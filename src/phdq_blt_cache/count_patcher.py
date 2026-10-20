"""Opt-in causal count model; independent of the BLT model and cache backends."""

from collections import deque
from dataclasses import asdict, dataclass
import math
import operator
import json
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class CountConfig:
    max_context: int = 8
    window: int | None = None
    alpha: float = 1.0
    kappa: float = 1.0
    suffix_decay: float = 1.0
    online_weight: float = 1.0
    vocab_size: int = 260
    eos_id: int = 2
    pad_id: int = 3

    def __post_init__(self):
        if type(self.max_context) is not int or self.max_context < 0:
            raise ValueError("max_context must be a nonnegative integer")
        if self.window is not None and (type(self.window) is not int or self.window < 1):
            raise ValueError("window must be a positive integer or None")
        if type(self.vocab_size) is not int or not 2 <= self.vocab_size <= 65536:
            raise ValueError("vocab_size must fit unsigned 16-bit IDs")
        if any(type(value) is not int or not 0 <= value < self.vocab_size for value in (self.eos_id, self.pad_id)) or self.eos_id == self.pad_id:
            raise ValueError("EOS and PAD must be distinct IDs in the vocabulary")
        if any(not math.isfinite(value) or value <= 0 for value in (self.alpha, self.kappa, self.suffix_decay)):
            raise ValueError("Smoothing and decay must be positive and finite")
        if self.suffix_decay > 1 or not math.isfinite(self.online_weight) or self.online_weight < 0:
            raise ValueError("Require decay <= 1 and finite online_weight >= 0")


def checked_id(value, config):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError("Boolean input is not a token ID")
    try:
        token_id = operator.index(value)
    except TypeError as error:
        raise ValueError("Input IDs must be integers") from error
    if not 0 <= token_id < config.vocab_size or token_id == config.pad_id:
        raise ValueError("Expected an unpadded in-vocabulary ID")
    return token_id


def contexts(history, maximum):
    yield b""
    for length in range(1, min(maximum, len(history) // 2) + 1):
        yield history[-2 * length:]


class CountTable:
    def __init__(self, config):
        self.config = config
        self._rows = {}
        self._totals = {}
        self._frozen = False

    def _adjust(self, context, token_id, delta):
        if self._frozen:
            raise ValueError("Background counts are frozen")
        row = self._rows.setdefault(context, {})
        count = row.get(token_id, 0) + delta
        if count < 0:
            raise ValueError("Count underflow")
        if count:
            row[token_id] = count
        else:
            row.pop(token_id, None)
        total = self._totals.get(context, 0) + delta
        if total:
            self._totals[context] = total
        else:
            self._totals.pop(context, None)
            self._rows.pop(context, None)

    def add_document(self, token_ids):
        if self._frozen:
            raise ValueError("Background counts are frozen")
        history = b""
        for value in token_ids:
            token_id = checked_id(value, self.config)
            for context in contexts(history, self.config.max_context):
                self._adjust(context, token_id, 1)
            history = (history + token_id.to_bytes(2, "little"))[-2 * self.config.max_context:] if self.config.max_context else b""
            if token_id == self.config.eos_id:
                history = b""

    def freeze(self):
        self._frozen = True
        return self

    def to_dict(self):
        return {
            "config": asdict(self.config),
            "rows": [[context.hex(), sorted(row.items())] for context, row in sorted(self._rows.items())],
        }

    def save(self, path):
        if not self._frozen:
            raise ValueError("Only frozen backgrounds can be saved")
        with Path(path).open("x") as stream:
            stream.write(json.dumps({"version": 1, "config": asdict(self.config)}) + "\n")
            for context, row in self._rows.items():
                stream.write(json.dumps([context.hex(), list(row.items())], separators=(",", ":")) + "\n")

    @classmethod
    def load(cls, path):
        with Path(path).open() as stream:
            metadata = json.loads(next(stream))
            if metadata["version"] != 1:
                raise ValueError("Unsupported background table version")
            return cls.from_dict({"config": metadata["config"], "rows": (json.loads(line) for line in stream)})

    @classmethod
    def from_dict(cls, payload):
        table = cls(CountConfig(**payload["config"]))
        for encoded, entries in payload["rows"]:
            context = bytes.fromhex(encoded)
            if len(context) % 2 or len(context) > 2 * table.config.max_context or context in table._rows:
                raise ValueError("Invalid or duplicate serialized context")
            for offset in range(0, len(context), 2):
                token_id = checked_id(int.from_bytes(context[offset:offset + 2], "little"), table.config)
                if token_id == table.config.eos_id:
                    raise ValueError("Context cannot cross EOS")
            for token_id, count in entries:
                token_id = checked_id(token_id, table.config)
                if type(count) is not int or count <= 0 or token_id in table._rows.get(context, {}):
                    raise ValueError("Serialized counts must be unique positive integers")
                table._adjust(context, token_id, count)
        return table.freeze()


class CountModel:
    def __init__(self, config, background=None):
        self.config = config
        if background is None:
            background = CountTable(config).freeze()
        if not background._frozen:
            raise ValueError("Freeze background counts before constructing a model")
        if background.config.max_context < config.max_context or any(
            getattr(background.config, name) != getattr(config, name)
            for name in ("vocab_size", "eos_id", "pad_id")
        ):
            raise ValueError("Background vocabulary and context capacity must match")
        self.background = background
        self.reset()

    def reset(self):
        self.online = CountTable(self.config)
        self.position = 0
        self._history = b""
        self._expiry = {}
        retained = None if self.config.window is None else self.config.window + self.config.max_context
        self._observed = deque(maxlen=retained)

    def observe(self, value):
        token_id = checked_id(value, self.config)
        maximum = self.config.max_context
        if self.config.window is not None:
            maximum = min(maximum, self.config.window - 1)
        for context in contexts(self._history, maximum):
            self.online._adjust(context, token_id, 1)
            if self.config.window is not None:
                start = self.position - len(context) // 2
                self._expiry.setdefault(start, []).append((context, token_id))
        self.position += 1
        self._observed.append(token_id)
        if self.config.window is not None:
            expired_start = self.position - self.config.window - 1
            for context, outcome in self._expiry.pop(expired_start, []):
                self.online._adjust(context, outcome, -1)
        self._history = (self._history + token_id.to_bytes(2, "little"))[-2 * self.config.max_context:] if self.config.max_context else b""
        if token_id == self.config.eos_id:
            self._history = b""

    def probabilities(self):
        probability = np.full(self.config.vocab_size, self.config.alpha / self.config.vocab_size, dtype=np.float64)
        total = self.config.alpha
        for table, weight in ((self.background, 1.0), (self.online, self.config.online_weight)):
            for token_id, count in table._rows.get(b"", {}).items():
                probability[token_id] += weight * count
            total += weight * table._totals.get(b"", 0)
        probability /= total
        weighted = probability.copy()
        normalizer = 1.0
        for context in contexts(self._history, self.config.max_context):
            if not context:
                continue
            probability = weighted / normalizer * self.config.kappa
            total = self.config.kappa
            for table, weight in ((self.background, 1.0), (self.online, self.config.online_weight)):
                for token_id, count in table._rows.get(context, {}).items():
                    probability[token_id] += weight * count
                total += weight * table._totals.get(context, 0)
            probability /= total
            weighted = self.config.suffix_decay * weighted + probability
            normalizer = self.config.suffix_decay * normalizer + 1
        return probability

    def features(self):
        probability = self.probabilities()
        entropy = float(-np.dot(probability, np.log(probability)))
        repeated_length = max(
            (len(context) // 2 for context in contexts(self._history, self.config.max_context)
             if self.online._totals.get(context, 0) > 0), default=0,
        )
        return entropy, repeated_length

    def state_dict(self):
        return {
            "version": 1, "config": asdict(self.config), "background": self.background.to_dict(),
            "position": self.position, "observed": list(self._observed),
        }

    @classmethod
    def from_state_dict(cls, payload):
        if payload["version"] != 1:
            raise ValueError("Unsupported count model state version")
        model = cls(CountConfig(**payload["config"]), CountTable.from_dict(payload["background"]))
        for token_id in payload["observed"]:
            model.observe(token_id)
        offset = payload["position"] - model.position
        if type(offset) is not int or offset < 0 or (model.config.window is None and offset):
            raise ValueError("Invalid serialized position")
        model.position += offset
        model._expiry = {start + offset: entries for start, entries in model._expiry.items()}
        return model


@dataclass(frozen=True)
class BoundaryRule:
    coefficients: tuple[float, float, float, float, float]
    mean_patch_length: float
    threshold: float = 0.5

    def __post_init__(self):
        if len(self.coefficients) != 5 or not all(math.isfinite(value) for value in self.coefficients):
            raise ValueError("Expected five finite boundary coefficients")
        if any(value < 0 for value in self.coefficients[1:]):
            raise ValueError("Non-intercept boundary coefficients must be nonnegative")
        if not math.isfinite(self.mean_patch_length) or self.mean_patch_length <= 0:
            raise ValueError("mean_patch_length must be positive and finite")
        if not math.isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError("threshold must be in [0, 1]")

    def score(self, distance, entropy, repeated_length):
        features = boundary_features(distance, self.mean_patch_length, entropy, repeated_length)
        logit = float(np.dot(features, self.coefficients))
        if not math.isfinite(logit):
            raise ValueError("Nonfinite boundary logit")
        return float(np.exp(-np.logaddexp(0.0, -logit)))


def boundary_features(distance, mean_patch_length, entropy, repeated_length):
    return np.array([1.0, distance, max(distance - mean_patch_length, 0.0) ** 2, entropy, -repeated_length])


@dataclass(frozen=True)
class BoundaryDecision:
    position: int
    entropy: float
    repeated_length: int
    distance: int
    score: float
    boundary: bool
    forced: bool


class SequentialPatcher:
    """Append only new IDs; prediction never observes the next ID."""

    def __init__(self, config, rule, background=None):
        self.model = CountModel(config, background)
        self.rule = rule
        self.last_boundary = 0

    def predict_boundary(self):
        position = self.model.position
        entropy, repeated_length = self.model.features()
        distance = position - self.last_boundary
        score = self.rule.score(distance, entropy, repeated_length)
        forced = position in (0, 1)
        return BoundaryDecision(position, entropy, repeated_length, distance, score, forced or score > self.rule.threshold, forced)

    def append(self, token_ids, *, start_position):
        if type(start_position) is not int or start_position != self.model.position:
            raise ValueError("Append must start at the next unobserved position")
        token_ids = [checked_id(value, self.model.config) for value in token_ids]
        decisions = []
        for token_id in token_ids:
            decision = self.predict_boundary()
            decisions.append(decision)
            if decision.boundary:
                self.last_boundary = decision.position
            self.model.observe(token_id)
        return decisions

    def state_dict(self):
        return {"model": self.model.state_dict(), "rule": asdict(self.rule), "last_boundary": self.last_boundary}

    @classmethod
    def from_state_dict(cls, payload):
        model = CountModel.from_state_dict(payload["model"])
        last_boundary = payload["last_boundary"]
        if type(last_boundary) is not int or not 0 <= last_boundary <= max(0, model.position - 1):
            raise ValueError("Invalid last boundary")
        patcher = cls(model.config, BoundaryRule(**payload["rule"]), model.background)
        patcher.model = model
        patcher.last_boundary = last_boundary
        return patcher


def rollout(token_ids, *, config, rule, background=None):
    token_ids = list(token_ids)
    if len(token_ids) < 2:
        raise ValueError("A BLT patching input needs at least two unpadded IDs")
    patcher = SequentialPatcher(config, rule, background)
    decisions = patcher.append(token_ids, start_position=0)
    decisions.append(patcher.predict_boundary())
    return decisions


def decision_patch_lengths(decisions):
    if len(decisions) < 3 or any(decision.position != position for position, decision in enumerate(decisions)):
        raise ValueError("Expected contiguous decisions including the virtual next-ID slot")
    if not all(decisions[position].boundary for position in (0, 1)):
        raise ValueError("BLT requires forced starts at positions 0 and 1")
    starts = [decision.position for decision in decisions if decision.boundary]
    return np.diff(starts + [len(decisions)]).tolist()


def teacher_features(token_ids, labels, *, config, mean_patch_length, background=None):
    token_ids = [checked_id(value, config) for value in token_ids]
    labels = list(labels)
    if len(token_ids) < 2 or len(labels) != len(token_ids) + 1:
        raise ValueError("Labels must include one virtual next-ID position")
    if any(value not in (0, 1) for value in labels) or labels[:2] != [1, 1]:
        raise ValueError("Expected binary teacher labels with forced starts 0 and 1")
    if not math.isfinite(mean_patch_length) or mean_patch_length <= 0:
        raise ValueError("mean_patch_length must be positive and finite")
    model = CountModel(config, background)
    last_boundary = 0
    features = []
    for position, label in enumerate(labels):
        entropy, repeated_length = model.features()
        features.append(boundary_features(position - last_boundary, mean_patch_length, entropy, repeated_length))
        if label:
            last_boundary = position
        if position < len(token_ids):
            model.observe(token_ids[position])
    mask = np.arange(len(labels)) >= 2
    return np.asarray(features), mask


def boundary_objective(coefficients, features, labels, rho):
    from scipy.special import expit

    logits = features @ coefficients
    loss = float(np.logaddexp(0.0, -(2 * labels - 1) * logits).mean() + rho / 2 * np.dot(coefficients, coefficients))
    gradient = features.T @ (expit(logits) - labels) / len(labels) + rho * coefficients
    if not math.isfinite(loss) or not np.isfinite(gradient).all():
        raise ValueError("Nonfinite boundary objective or gradient")
    return loss, gradient


def fit_boundary(features, labels, *, rho, maximum_iterations=500):
    from scipy.optimize import minimize

    features = np.asarray(features, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    if features.ndim != 2 or features.shape[1] != 5 or labels.shape != (len(features),) or not len(labels):
        raise ValueError("Expected a nonempty five-column fixed-feature matrix")
    if not np.isfinite(features).all() or not np.isin(labels, (0, 1)).all():
        raise ValueError("Invalid features or binary labels")
    if not math.isfinite(rho) or rho <= 0:
        raise ValueError("rho must be positive and finite, including for the intercept")
    scale = np.maximum(np.sqrt(np.mean(features ** 2, axis=0)), 1.0)
    scaled = features / scale

    def objective(parameters):
        coefficients = parameters / scale
        logits = scaled @ parameters
        from scipy.special import expit

        loss = float(np.logaddexp(0.0, -(2 * labels - 1) * logits).mean() + rho / 2 * np.dot(coefficients, coefficients))
        gradient = scaled.T @ (expit(logits) - labels) / len(labels) + rho * coefficients / scale
        if not math.isfinite(loss) or not np.isfinite(gradient).all():
            raise ValueError("Nonfinite scaled objective")
        return loss, gradient

    result = minimize(objective, np.zeros(5), method="L-BFGS-B", jac=True,
                      bounds=[(None, None)] + [(0, None)] * 4,
                      options={"maxiter": maximum_iterations, "ftol": 1e-12, "gtol": 1e-8})
    coefficients = result.x / scale
    loss, gradient = boundary_objective(coefficients, features, labels, rho)
    projected = gradient.copy()
    for index in range(1, 5):
        if coefficients[index] <= 1e-12 and gradient[index] > 0:
            projected[index] = 0
    if not result.success or np.any(coefficients[1:] < 0) or np.max(np.abs(projected / scale)) > 1e-5:
        raise RuntimeError(f"Boundary optimizer did not converge: {result.message}")
    return {
        "coefficients": coefficients.tolist(), "rho": rho, "loss": loss,
        "iterations": int(result.nit), "evaluations": int(result.nfev), "message": str(result.message),
        "feature_scale": scale.tolist(), "gradient": gradient.tolist(),
        "scaled_projected_gradient_max": float(np.max(np.abs(projected / scale))),
    }