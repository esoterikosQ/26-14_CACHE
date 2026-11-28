// Native builder for phdq_count_lmdb_v1 backgrounds: key-range passes over count blocks, sorted MDB_APPEND writes.
#include <sys/statvfs.h>
#include <zlib.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <queue>
#include <string>
#include <thread>
#include <vector>

// liblmdb 0.9 C ABI; the runtime library is present but its development header is not installed.
extern "C" {
typedef struct MDB_env MDB_env;
typedef struct MDB_txn MDB_txn;
typedef unsigned int MDB_dbi;
typedef struct MDB_val {
    size_t mv_size;
    void* mv_data;
} MDB_val;
int mdb_env_create(MDB_env** env);
int mdb_env_set_mapsize(MDB_env* env, size_t size);
int mdb_env_open(MDB_env* env, const char* path, unsigned int flags, unsigned int mode);
int mdb_txn_begin(MDB_env* env, MDB_txn* parent, unsigned int flags, MDB_txn** txn);
int mdb_dbi_open(MDB_txn* txn, const char* name, unsigned int flags, MDB_dbi* dbi);
int mdb_put(MDB_txn* txn, MDB_dbi dbi, MDB_val* key, MDB_val* data, unsigned int flags);
int mdb_txn_commit(MDB_txn* txn);
void mdb_txn_abort(MDB_txn* txn);
int mdb_env_sync(MDB_env* env, int force);
void mdb_env_close(MDB_env* env);
char* mdb_strerror(int error);
}

namespace {

const unsigned int MDB_NOSYNC = 0x10000, MDB_NOMETASYNC = 0x40000, MDB_APPEND = 0x20000;
const uint32_t NONE = 0xffffffffu;
const size_t SHARDS = 4096;

uint64_t mix(uint64_t value) {
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}

struct Key {
    uint8_t bytes[16];
    uint8_t length;
};

// LMDB/Python bytes order: lexicographic, then shorter first; zero padding keeps this exact.
int compare(const Key& a, const Key& b) {
    int c = std::memcmp(a.bytes, b.bytes, 16);
    if (c) return c;
    return int(a.length) - int(b.length);
}

uint64_t hash(const Key& key) {
    uint64_t low, high;
    std::memcpy(&low, key.bytes, 8);
    std::memcpy(&high, key.bytes + 8, 8);
    return mix(low ^ mix(high ^ mix(key.length)));
}

struct Entry {
    uint64_t count;
    uint32_t next;
    uint16_t token;
};

struct Shard {
    std::mutex mutex;
    std::vector<uint32_t> slots;
    std::vector<Key> keys;
    std::vector<uint32_t> head;
    std::vector<Entry> entries;
    size_t mask = 0;

    void reset() {
        std::vector<uint32_t>().swap(slots);
        std::vector<Key>().swap(keys);
        std::vector<uint32_t>().swap(head);
        std::vector<Entry>().swap(entries);
        slots.assign(256, NONE);
        mask = 255;
    }

    uint32_t find_or_insert(const Key& key, uint64_t h) {
        if ((keys.size() + 1) * 2 > slots.size()) grow();
        size_t slot = (h >> 12) & mask;
        while (slots[slot] != NONE) {
            if (compare(keys[slots[slot]], key) == 0) return slots[slot];
            slot = (slot + 1) & mask;
        }
        slots[slot] = uint32_t(keys.size());
        keys.push_back(key);
        head.push_back(NONE);
        return slots[slot];
    }

    void grow() {
        std::vector<uint32_t>(slots.size() * 2, NONE).swap(slots);
        mask = slots.size() - 1;
        for (uint32_t row = 0; row < keys.size(); ++row) {
            size_t slot = (hash(keys[row]) >> 12) & mask;
            while (slots[slot] != NONE) slot = (slot + 1) & mask;
            slots[slot] = row;
        }
    }

    bool add(uint32_t row, uint16_t token, uint64_t count) {
        for (uint32_t index = head[row]; index != NONE; index = entries[index].next) {
            if (entries[index].token == token) {
                if (entries[index].count > ~0ULL - count) return false;
                entries[index].count += count;
                return true;
            }
        }
        Entry entry = {count, head[row], token};
        head[row] = uint32_t(entries.size());
        entries.push_back(entry);
        return entries.size() < NONE;
    }

    uint64_t bytes() const {
        return slots.capacity() * 4 + keys.capacity() * sizeof(Key) + head.capacity() * 4 + entries.capacity() * sizeof(Entry);
    }
};

struct Range {
    bool has_low = false, has_high = false;
    Key low{}, high{};
    bool contains(const Key& key) const {
        return (!has_low || compare(key, low) >= 0) && (!has_high || compare(key, high) < 0);
    }
};

uint64_t rss_bytes() {
    FILE* file = std::fopen("/proc/self/statm", "r");
    if (!file) return 0;
    unsigned long pages = 0, resident = 0;
    int read = std::fscanf(file, "%lu %lu", &pages, &resident);
    std::fclose(file);
    return read == 2 ? uint64_t(resident) * 4096 : 0;
}

class Builder {
public:
    Builder(const char* header, uint64_t header_length, int vocab, int pad, int eos, int max_context, int threads,
            const char* paths, uint64_t path_count)
        : header_(header, size_t(header_length)), vocab_(vocab), pad_(pad), eos_(eos), max_context_(max_context),
          threads_(std::max(1, threads)), shards_(SHARDS) {
        std::string list(paths);
        size_t start = 0;
        while (paths_.size() < path_count) {
            size_t end = list.find('\n', start);
            if (end == std::string::npos) end = list.size();
            paths_.push_back(list.substr(start, end - start));
            start = end + 1;
        }
        rows_.assign(paths_.size(), 0);
    }

    std::string error;

    bool sample(uint32_t modulus, uint64_t* rows_per_block, uint64_t* sample_keys, uint64_t* sample_entries) {
        modulus_ = modulus;
        Range all;
        mode_ = SAMPLE;
        reset_shards();
        if (!scan(all)) return false;
        std::memcpy(rows_per_block, rows_.data(), rows_.size() * 8);
        sample_.clear();
        uint64_t entries = 0;
        for (Shard& shard : shards_) {
            sample_.insert(sample_.end(), shard.keys.begin(), shard.keys.end());
            entries += shard.entries.size();
        }
        std::sort(sample_.begin(), sample_.end(), [](const Key& a, const Key& b) { return compare(a, b) < 0; });
        *sample_keys = sample_.size();
        *sample_entries = entries;
        reset_shards();
        return true;
    }

    bool plan(uint32_t passes) {
        if (passes < 1 || sample_.size() < passes) { error = "Too few sampled keys for the requested passes"; return false; }
        ranges_.assign(passes, Range());
        for (uint32_t i = 1; i < passes; ++i) {
            const Key& boundary = sample_[size_t(i) * sample_.size() / passes];
            ranges_[i - 1].has_high = true;
            ranges_[i - 1].high = boundary;
            ranges_[i].has_low = true;
            ranges_[i].low = boundary;
        }
        return true;
    }

    bool write(const char* output, uint64_t map_size, uint64_t min_free, uint64_t max_output, uint64_t max_rss,
               const uint8_t* metadata, uint64_t metadata_length, uint64_t* contexts, uint64_t* rows) {
        MDB_env* env = 0;
        int rc = mdb_env_create(&env);
        if (!rc) rc = mdb_env_set_mapsize(env, size_t(map_size));
        if (!rc) rc = mdb_env_open(env, output, MDB_NOSYNC | MDB_NOMETASYNC, 0644);
        if (rc) { error = std::string("LMDB open failed: ") + mdb_strerror(rc); if (env) mdb_env_close(env); return false; }
        output_ = output;
        MDB_txn* txn = 0;
        MDB_dbi dbi = 0;
        rc = mdb_txn_begin(env, 0, 0, &txn);
        if (!rc) rc = mdb_dbi_open(txn, 0, 0, &dbi);
        MDB_val mkey = {9, const_cast<char*>("\x00metadata")}, mval = {size_t(metadata_length), const_cast<uint8_t*>(metadata)};
        if (!rc) rc = mdb_put(txn, dbi, &mkey, &mval, 0);
        if (!rc) rc = mdb_txn_commit(txn);
        txn = 0;
        if (rc) { error = std::string("LMDB metadata failed: ") + mdb_strerror(rc); mdb_env_close(env); return false; }
        uint64_t written = 0, input_rows = 0;
        bool ok = true;
        for (size_t pass = 0; pass < ranges_.size() && ok; ++pass) {
            auto started = std::chrono::steady_clock::now();
            mode_ = AGGREGATE;
            reset_shards();
            rows_.assign(paths_.size(), 0);
            in_range_ = 0;
            ok = scan(ranges_[pass]);
            if (!ok) break;
            input_rows += in_range_;
            uint64_t memory = 0, keys = 0;
            for (Shard& shard : shards_) { memory += shard.bytes(); keys += shard.keys.size(); }
            uint64_t resident = rss_bytes();
            if (max_rss && resident > max_rss) { error = "Native LMDB RSS limit reached; use more passes"; ok = false; break; }
            ok = emit(env, dbi, min_free, max_output, &written);
            double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
            std::printf("{\"stage\": \"pass\", \"pass\": %zu, \"passes\": %zu, \"keys\": %llu, \"rows\": %llu, "
                        "\"aggregate_bytes\": %llu, \"rss_bytes\": %llu, \"written\": %llu, \"seconds\": %.1f}\n",
                        pass + 1, ranges_.size(), (unsigned long long)keys, (unsigned long long)in_range_,
                        (unsigned long long)memory, (unsigned long long)resident, (unsigned long long)written, seconds);
            std::fflush(stdout);
        }
        reset_shards();
        if (ok && (rc = mdb_env_sync(env, 1))) { error = std::string("LMDB sync failed: ") + mdb_strerror(rc); ok = false; }
        mdb_env_close(env);
        *contexts = written;
        *rows = input_rows;
        return ok;
    }

private:
    enum Mode { SAMPLE, AGGREGATE };

    void reset_shards() {
        for (Shard& shard : shards_) shard.reset();
    }

    bool scan(const Range& range) {
        std::atomic<size_t> next(0);
        std::atomic<bool> failed(false);
        std::mutex error_mutex;
        std::vector<std::thread> workers;
        for (int t = 0; t < threads_; ++t) {
            workers.emplace_back([&]() {
                std::vector<std::pair<uint16_t, uint64_t>> row;
                while (!failed) {
                    size_t block = next.fetch_add(1);
                    if (block >= paths_.size()) break;
                    std::string message;
                    uint64_t count = 0, in_range = 0;
                    if (!read_block(block, range, row, count, in_range, message)) {
                        std::lock_guard<std::mutex> lock(error_mutex);
                        if (!failed.exchange(true)) error = paths_[block] + ": " + message;
                        break;
                    }
                    rows_[block] = count;
                    in_range_ += in_range;
                }
            });
        }
        for (std::thread& worker : workers) worker.join();
        return !failed;
    }

    bool read_block(size_t block, const Range& range, std::vector<std::pair<uint16_t, uint64_t>>& row,
                    uint64_t& count, uint64_t& in_range, std::string& message) {
        gzFile file = gzopen(paths_[block].c_str(), "rb");
        if (!file) { message = "open failed"; return false; }
        gzbuffer(file, 1u << 20);
        std::vector<char> buffer(1u << 22);
        std::string pending;
        bool header = false, ok = true;
        while (ok) {
            int read = gzread(file, buffer.data(), unsigned(buffer.size()));
            if (read < 0) { message = "read failed"; ok = false; break; }
            if (read == 0) break;
            pending.append(buffer.data(), size_t(read));
            size_t start = 0;
            while (ok) {
                size_t end = pending.find('\n', start);
                if (end == std::string::npos) break;
                ok = line(pending.data() + start, end - start, header, range, row, count, in_range, message);
                start = end + 1;
            }
            pending.erase(0, start);
        }
        if (ok && !pending.empty()) ok = line(pending.data(), pending.size(), header, range, row, count, in_range, message);
        if (gzclose(file) != Z_OK && ok) { message = "close failed"; ok = false; }
        if (ok && !header) { message = "Background block configuration mismatch"; ok = false; }
        return ok;
    }

    static int hex(char c) {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        return -1;
    }

    static bool integer(const char*& p, const char* end, uint64_t& value) {
        if (p == end || *p < '0' || *p > '9') return false;
        value = 0;
        while (p < end && *p >= '0' && *p <= '9') {
            uint64_t digit = uint64_t(*p - '0');
            if (value > (~0ULL - digit) / 10) return false;
            value = value * 10 + digit;
            ++p;
        }
        return true;
    }

    bool line(const char* text, size_t length, bool& header, const Range& range,
              std::vector<std::pair<uint16_t, uint64_t>>& row, uint64_t& count, uint64_t& in_range, std::string& message) {
        if (!header) {
            header = true;
            if (length != header_.size() || std::memcmp(text, header_.data(), length)) {
                message = "Background block configuration mismatch";
                return false;
            }
            return true;
        }
        ++count;
        const char* p = text;
        const char* end = text + length;
        if (length < 7 || p[0] != '[' || p[1] != '"') { message = "Invalid background row"; return false; }
        p += 2;
        const char* start = p;
        while (p < end && *p != '"') ++p;
        size_t digits = size_t(p - start);
        if (p == end || digits % 2 || digits / 2 > size_t(2 * max_context_) || digits / 2 > 16) {
            message = "Invalid background context";
            return false;
        }
        Key key;
        std::memset(&key, 0, sizeof(key));
        key.length = uint8_t(digits / 2);
        for (size_t i = 0; i < digits; i += 2) {
            int high = hex(start[i]), low = hex(start[i + 1]);
            if (high < 0 || low < 0) { message = "Invalid background context"; return false; }
            key.bytes[i / 2] = uint8_t(high * 16 + low);
        }
        uint64_t h = hash(key);
        bool sampled = mode_ == SAMPLE ? (h & (modulus_ - 1)) == 0 : range.contains(key);
        if (!sampled) return true;
        for (size_t i = 0; i < key.length; i += 2) {
            int id = key.bytes[i] | (key.bytes[i + 1] << 8);
            if (id >= vocab_ || id == pad_) { message = "Expected an unpadded in-vocabulary ID"; return false; }
            if (id == eos_) { message = "Context cannot cross EOS"; return false; }
        }
        ++p;
        if (end - p < 3 || p[0] != ',' || p[1] != '[') { message = "Invalid background row"; return false; }
        p += 2;
        row.clear();
        uint64_t seen[5] = {0, 0, 0, 0, 0};
        bool first = true;
        while (p < end && *p != ']') {
            if (!first && *p++ != ',') { message = "Invalid background row"; return false; }
            first = false;
            uint64_t token = 0, value = 0;
            if (p == end || *p++ != '[' || !integer(p, end, token) || p == end || *p++ != ',' ||
                !integer(p, end, value) || p == end || *p++ != ']') {
                message = "Invalid background row";
                return false;
            }
            if (token >= uint64_t(vocab_) || int(token) == pad_) { message = "Expected an unpadded in-vocabulary ID"; return false; }
            if (value == 0) { message = "Invalid serialized count"; return false; }
            uint64_t bit = 1ULL << (token & 63);
            if (seen[token >> 6] & bit) { message = "Invalid serialized count"; return false; }
            seen[token >> 6] |= bit;
            row.emplace_back(uint16_t(token), value);
        }
        if (end - p != 2 || p[0] != ']' || p[1] != ']') { message = "Invalid background row"; return false; }
        ++in_range;
        Shard& shard = shards_[mix(h) % SHARDS];
        std::lock_guard<std::mutex> lock(shard.mutex);
        uint32_t index = shard.find_or_insert(key, h);
        for (size_t i = 0; i < row.size(); ++i)
            if (!shard.add(index, row[i].first, row[i].second)) { message = "Count overflow or shard capacity exceeded"; return false; }
        if (shard.keys.size() >= NONE) { message = "Shard capacity exceeded"; return false; }
        return true;
    }

    bool emit(MDB_env* env, MDB_dbi dbi, uint64_t min_free, uint64_t max_output, uint64_t* written) {
        std::vector<std::vector<uint32_t>> orders(SHARDS);
        {
            std::atomic<size_t> next(0);
            std::vector<std::thread> workers;
            for (int t = 0; t < threads_; ++t) {
                workers.emplace_back([&]() {
                    for (size_t s = next.fetch_add(1); s < SHARDS; s = next.fetch_add(1)) {
                        Shard& shard = shards_[s];
                        std::vector<uint32_t>& order = orders[s];
                        order.resize(shard.keys.size());
                        for (uint32_t i = 0; i < order.size(); ++i) order[i] = i;
                        std::sort(order.begin(), order.end(), [&](uint32_t a, uint32_t b) {
                            return compare(shard.keys[a], shard.keys[b]) < 0;
                        });
                        std::vector<uint32_t>().swap(shard.slots);
                    }
                });
            }
            for (std::thread& worker : workers) worker.join();
        }
        typedef std::pair<uint32_t, uint32_t> Cursor;  // shard, position
        auto greater = [&](const Cursor& a, const Cursor& b) {
            return compare(shards_[a.first].keys[orders[a.first][a.second]], shards_[b.first].keys[orders[b.first][b.second]]) > 0;
        };
        std::priority_queue<Cursor, std::vector<Cursor>, decltype(greater)> heap(greater);
        for (uint32_t s = 0; s < SHARDS; ++s)
            if (!orders[s].empty()) heap.push(Cursor(s, 0));
        MDB_txn* txn = 0;
        int rc = mdb_txn_begin(env, 0, 0, &txn);
        if (rc) { error = std::string("LMDB txn failed: ") + mdb_strerror(rc); return false; }
        uint8_t key_bytes[17];
        std::vector<uint8_t> value;
        std::vector<std::pair<uint16_t, uint64_t>> row;
        uint64_t in_txn = 0;
        bool has_previous = false;
        Key previous{};
        while (!heap.empty()) {
            Cursor cursor = heap.top();
            heap.pop();
            Shard& shard = shards_[cursor.first];
            uint32_t index = orders[cursor.first][cursor.second];
            const Key& key = shard.keys[index];
            if (has_previous && compare(previous, key) >= 0) { error = "Key order violated"; mdb_txn_abort(txn); return false; }
            previous = key;
            has_previous = true;
            row.clear();
            for (uint32_t e = shard.head[index]; e != NONE; e = shard.entries[e].next)
                row.emplace_back(shard.entries[e].token, shard.entries[e].count);
            std::sort(row.begin(), row.end());
            value.resize(row.size() * 10);
            for (size_t i = 0; i < row.size(); ++i) {
                std::memcpy(&value[10 * i], &row[i].first, 2);
                std::memcpy(&value[10 * i + 2], &row[i].second, 8);
            }
            key_bytes[0] = 1;
            std::memcpy(key_bytes + 1, key.bytes, key.length);
            MDB_val k = {size_t(key.length) + 1, key_bytes}, v = {value.size(), value.data()};
            rc = mdb_put(txn, dbi, &k, &v, MDB_APPEND);
            if (rc) { error = std::string("LMDB put failed: ") + mdb_strerror(rc); mdb_txn_abort(txn); return false; }
            ++*written;
            if (++in_txn == 1000000) {
                rc = mdb_txn_commit(txn);
                txn = 0;
                if (!rc) rc = mdb_txn_begin(env, 0, 0, &txn);
                if (rc) { error = std::string("LMDB commit failed: ") + mdb_strerror(rc); if (txn) mdb_txn_abort(txn); return false; }
                in_txn = 0;
                if (!storage_ok(min_free, max_output)) { mdb_txn_abort(txn); return false; }
            }
            if (cursor.second + 1 < orders[cursor.first].size()) heap.push(Cursor(cursor.first, cursor.second + 1));
        }
        rc = mdb_txn_commit(txn);
        if (rc) { error = std::string("LMDB commit failed: ") + mdb_strerror(rc); return false; }
        return storage_ok(min_free, max_output);
    }

    bool storage_ok(uint64_t min_free, uint64_t max_output) {
        struct statvfs fs;
        if (statvfs(output_.c_str(), &fs)) { error = "statvfs failed"; return false; }
        if (uint64_t(fs.f_bavail) * fs.f_frsize < min_free) { error = "LMDB minimum free disk guard reached"; return false; }
        std::string data = output_ + "/data.mdb";
        FILE* file = std::fopen(data.c_str(), "rb");
        if (file) {
            std::fseek(file, 0, SEEK_END);
            long size = std::ftell(file);
            std::fclose(file);
            if (max_output && uint64_t(size) > max_output) { error = "LMDB maximum output guard reached"; return false; }
        }
        return true;
    }

    std::string header_;
    int vocab_, pad_, eos_, max_context_, threads_;
    std::vector<std::string> paths_;
    std::vector<uint64_t> rows_;
    std::vector<Shard> shards_;
    std::vector<Key> sample_;
    std::vector<Range> ranges_;
    std::atomic<uint64_t> in_range_{0};
    uint32_t modulus_ = 1;
    Mode mode_ = SAMPLE;
    std::string output_;
};

void copy_error(const std::string& message, char* error, uint64_t size) {
    if (!size) return;
    size_t n = std::min<size_t>(message.size(), size - 1);
    std::memcpy(error, message.data(), n);
    error[n] = 0;
}

}  // namespace

extern "C" {

void* bl_new(const char* header, uint64_t header_length, int vocab, int pad, int eos, int max_context, int threads,
             const char* paths, uint64_t path_count) {
    return new Builder(header, header_length, vocab, pad, eos, max_context, threads, paths, path_count);
}

void bl_free(void* builder) { delete static_cast<Builder*>(builder); }

int bl_sample(void* handle, uint32_t modulus, uint64_t* rows_per_block, uint64_t* sample_keys, uint64_t* sample_entries,
              char* error, uint64_t error_size) {
    Builder* builder = static_cast<Builder*>(handle);
    if (!modulus || (modulus & (modulus - 1))) { copy_error("Sample modulus must be a power of two", error, error_size); return 1; }
    if (builder->sample(modulus, rows_per_block, sample_keys, sample_entries)) return 0;
    copy_error(builder->error, error, error_size);
    return 1;
}

int bl_plan(void* handle, uint32_t passes, char* error, uint64_t error_size) {
    Builder* builder = static_cast<Builder*>(handle);
    if (builder->plan(passes)) return 0;
    copy_error(builder->error, error, error_size);
    return 1;
}

int bl_write(void* handle, const char* output, uint64_t map_size, uint64_t min_free, uint64_t max_output, uint64_t max_rss,
             const uint8_t* metadata, uint64_t metadata_length, uint64_t* contexts, uint64_t* rows,
             char* error, uint64_t error_size) {
    Builder* builder = static_cast<Builder*>(handle);
    if (builder->write(output, map_size, min_free, max_output, max_rss, metadata, metadata_length, contexts, rows)) return 0;
    copy_error(builder->error, error, error_size);
    return 1;
}

}  // extern "C"
