#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

struct Row {
    std::unordered_map<int, double> counts;
    double total = 0;
};

struct Decision {
    double entropy;
    double score;
    int repeated;
    int distance;
    bool boundary;
};

struct State {
    int maximum;
    double alpha, kappa, decay, weight, mean, threshold;
    std::array<double, 5> coefficients;
    PyObject* lookup = nullptr;
    std::unordered_map<std::string, Row> online;
    std::string history;
    std::vector<int> ids;
    std::vector<Decision> decisions;
    int last_boundary = 0;
    ~State() { Py_XDECREF(lookup); }

    void add_background(std::array<double, 260>& probability, double& total,
                        const std::string& context) {
        PyObject* key = PyBytes_FromStringAndSize(context.data(), context.size());
        PyObject* result = PyObject_CallOneArg(lookup, key);
        Py_DECREF(key);
        if (!result) throw std::runtime_error("Background lookup failed");
        PyObject* items = PyMapping_Items(PyTuple_GetItem(result, 0));
        if (!items) { Py_DECREF(result); throw std::runtime_error("Invalid row"); }
        for (Py_ssize_t index = 0; index < PyList_GET_SIZE(items); ++index) {
            PyObject* entry = PyList_GET_ITEM(items, index);
            long token = PyLong_AsLong(PyTuple_GET_ITEM(entry, 0));
            double count = PyLong_AsDouble(PyTuple_GET_ITEM(entry, 1));
            if (PyErr_Occurred() || token < 0 || token >= 260) {
                Py_DECREF(items); Py_DECREF(result);
                throw std::runtime_error("Invalid background count");
            }
            probability[token] += count;
        }
        total += PyLong_AsDouble(PyTuple_GetItem(result, 1));
        Py_DECREF(items);
        Py_DECREF(result);
        if (PyErr_Occurred()) throw std::runtime_error("Invalid total");
    }

    void add_counts(std::array<double, 260>& probability, double& total,
                    const std::string& context) {
        add_background(probability, total, context);
        auto found = online.find(context);
        if (found != online.end()) {
            for (const auto& entry : found->second.counts)
                probability[entry.first] += weight * entry.second;
            total += weight * found->second.total;
        }
    }

    Decision predict() {
        std::array<double, 260> probability, weighted;
        probability.fill(alpha / 260.0);
        double total = alpha;
        add_counts(probability, total, "");
        for (int token = 0; token < 260; ++token) probability[token] /= total;
        weighted = probability;
        double normalizer = 1.0;
        int repeated = 0;
        int capacity = std::min(maximum, static_cast<int>(history.size() / 2));
        for (int length = 1; length <= capacity; ++length) {
            std::string context = history.substr(history.size() - 2 * length);
            auto found = online.find(context);
            if (found != online.end() && found->second.total > 0) repeated = length;
            for (int token = 0; token < 260; ++token)
                probability[token] = weighted[token] / normalizer * kappa;
            total = kappa;
            add_counts(probability, total, context);
            for (int token = 0; token < 260; ++token) {
                probability[token] /= total;
                weighted[token] = decay * weighted[token] + probability[token];
            }
            normalizer = decay * normalizer + 1.0;
        }
        double entropy = 0;
        for (int token = 0; token < 260; ++token) {
            entropy -= probability[token] * std::log(probability[token]);
        }
        int position = static_cast<int>(ids.size());
        int distance = position - last_boundary;
        double excess = std::max(distance - mean, 0.0);
        std::array<double, 5> features = {1., static_cast<double>(distance), excess * excess,
                                         entropy, -static_cast<double>(repeated)};
        double logit = 0;
        for (int index = 0; index < 5; ++index) logit += features[index] * coefficients[index];
        double score = std::exp(-(std::max(0.0, -logit) + std::log1p(std::exp(-std::abs(logit)))));
        return {entropy, score, repeated, distance, position < 2 || score > threshold};
    }

    void observe(int token) {
        int capacity = std::min(maximum, static_cast<int>(history.size() / 2));
        for (int length = 0; length <= capacity; ++length) {
            std::string context = history.substr(history.size() - 2 * length);
            Row& row = online[context];
            row.counts[token] += 1.0;
            row.total += 1.0;
        }
        ids.push_back(token);
        history.push_back(static_cast<char>(token & 255));
        history.push_back(static_cast<char>((token >> 8) & 255));
        if (history.size() > static_cast<size_t>(2 * maximum))
            history.erase(0, history.size() - 2 * maximum);
        if (token == 2) history.clear();
    }
};

static void destroy(PyObject* capsule) {
    delete static_cast<State*>(PyCapsule_GetPointer(capsule, "count_state"));
}

static double number(PyObject* dictionary, const char* key) {
    PyObject* value = PyDict_GetItemString(dictionary, key);
    if (!value) throw std::runtime_error("Missing configuration key");
    double result = PyFloat_AsDouble(value);
    if (PyErr_Occurred()) throw std::runtime_error("Invalid configuration value");
    return result;
}

static PyObject* create(PyObject*, PyObject* args) {
    PyObject *config, *rule, *lookup;
    if (!PyArg_ParseTuple(args, "OOO", &config, &rule, &lookup)) return nullptr;
    State* state = new State();
    try {
        state->maximum = static_cast<int>(number(config, "max_context"));
        state->alpha = number(config, "alpha"); state->kappa = number(config, "kappa");
        state->decay = number(config, "suffix_decay"); state->weight = number(config, "online_weight");
        state->mean = number(rule, "mean_patch_length"); state->threshold = number(rule, "threshold");
        PyObject* coefficients = PyDict_GetItemString(rule, "coefficients");
        if (!coefficients || PySequence_Size(coefficients) != 5 || !PyCallable_Check(lookup))
            throw std::runtime_error("Invalid rule or lookup");
        for (int index = 0; index < 5; ++index) {
            PyObject* value = PySequence_GetItem(coefficients, index);
            state->coefficients[index] = PyFloat_AsDouble(value); Py_DECREF(value);
        }
        Py_INCREF(lookup); state->lookup = lookup;
        if (PyErr_Occurred()) throw std::runtime_error("Invalid coefficients");
        return PyCapsule_New(state, "count_state", destroy);
    } catch (const std::exception& error) {
        delete state;
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_ValueError, error.what());
        return nullptr;
    }
}

static PyObject* run(PyObject*, PyObject* args) {
    PyObject *capsule, *input;
    int details = 0;
    if (!PyArg_ParseTuple(args, "OO|p", &capsule, &input, &details)) return nullptr;
    auto* state = static_cast<State*>(PyCapsule_GetPointer(capsule, "count_state"));
    if (!state) return nullptr;
    PyObject* sequence = PySequence_Fast(input, "Expected token IDs");
    if (!sequence) return nullptr;
    try {
        Py_ssize_t size = PySequence_Fast_GET_SIZE(sequence);
        if (size < 2) throw std::runtime_error("Expected at least two IDs");
        std::vector<int> ids;
        for (Py_ssize_t index = 0; index < size; ++index) {
            PyObject* value = PySequence_Fast_GET_ITEM(sequence, index);
            if (!PyLong_Check(value) || PyBool_Check(value)) throw std::runtime_error("Invalid ID type");
            long token = PyLong_AsLong(value);
            if (PyErr_Occurred() || token < 0 || token >= 260 || token == 3)
                throw std::runtime_error("Invalid token ID");
            ids.push_back(static_cast<int>(token));
        }
        if (ids.size() < state->ids.size() || !std::equal(state->ids.begin(), state->ids.end(), ids.begin())) {
            state->online.clear(); state->history.clear(); state->ids.clear();
            state->decisions.clear(); state->last_boundary = 0;
        }
        for (size_t position = state->ids.size(); position < ids.size(); ++position) {
            Decision decision = state->predict();
            state->decisions.push_back(decision);
            if (decision.boundary) state->last_boundary = static_cast<int>(position);
            state->observe(ids[position]);
        }
        auto decisions = state->decisions;
        decisions.push_back(state->predict());
        std::vector<int> starts;
        for (size_t position = 0; position < decisions.size(); ++position)
            if (decisions[position].boundary) starts.push_back(static_cast<int>(position));
        starts.push_back(static_cast<int>(decisions.size()));
        PyObject* lengths = PyList_New(starts.size() - 1);
        for (size_t index = 1; index < starts.size(); ++index)
            PyList_SET_ITEM(lengths, index - 1, PyLong_FromLong(starts[index] - starts[index - 1]));
        Py_DECREF(sequence);
        if (!details) return lengths;
        PyObject* diagnostics = PyList_New(decisions.size());
        for (size_t index = 0; index < decisions.size(); ++index) {
            const auto& decision = decisions[index];
            PyList_SET_ITEM(diagnostics, index, Py_BuildValue("ddiii", decision.entropy, decision.score,
                decision.repeated, decision.distance, decision.boundary));
        }
        return Py_BuildValue("NN", lengths, diagnostics);
    } catch (const std::exception& error) {
        Py_DECREF(sequence);
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_ValueError, error.what());
        return nullptr;
    }
}

static PyMethodDef methods[] = {
    {"create", create, METH_VARARGS, "Create experimental frozen count state."},
    {"run", run, METH_VARARGS, "Process an entire prefix; optionally return diagnostics."},
    {nullptr, nullptr, 0, nullptr}
};
static PyModuleDef module = {PyModuleDef_HEAD_INIT, "_count_patcher_probe", nullptr, -1, methods};
PyMODINIT_FUNC PyInit__count_patcher_probe() { return PyModule_Create(&module); }