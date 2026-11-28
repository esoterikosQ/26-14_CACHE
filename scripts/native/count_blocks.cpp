// Opt-in kernels reproducing CountTable block files and required-context projections.
#include <zlib.h>
#include <fcntl.h>
#include <unistd.h>

#include <cerrno>
#include <cstdint>
#include <cstring>
#include <new>
#include <string>
#include <utility>
#include <vector>

namespace {

constexpr uint32_t NONE = 0xffffffffu;
constexpr int MAX_CONTEXT = 32;

enum Error : int {
    OK = 0,
    INVALID_ARGUMENT = -1,
    INVALID_TOKEN = -2,
    OPEN_FAILED = -3,
    WRITE_FAILED = -4,
    OUT_OF_MEMORY = -5,
    OVERFLOW = -6,
    READ_FAILED = -7,
    HEADER_MISMATCH = -8,
    PARSE_FAILED = -9,
    STATE_FAILED = -10,
};

inline uint64_t mix(uint64_t value) {
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}

class IndexMap {
public:
    IndexMap() { reset(1u << 16); }

    uint32_t find_or_insert(uint64_t key, uint32_t candidate, bool& inserted) {
        if ((size_ + 1) * 2 > keys_.size()) grow();
        size_t slot = mix(key) & mask_;
        while (true) {
            if (keys_[slot] == key) {
                inserted = false;
                return values_[slot];
            }
            if (keys_[slot] == EMPTY) {
                keys_[slot] = key;
                values_[slot] = candidate;
                ++size_;
                inserted = true;
                return candidate;
            }
            slot = (slot + 1) & mask_;
        }
    }

private:
    static constexpr uint64_t EMPTY = ~0ULL;

    void reset(size_t capacity) {
        keys_.assign(capacity, EMPTY);
        values_.assign(capacity, 0);
        mask_ = capacity - 1;
        size_ = 0;
    }

    void grow() {
        std::vector<uint64_t> keys;
        std::vector<uint32_t> values;
        keys.swap(keys_);
        values.swap(values_);
        reset(keys.size() * 2);
        bool inserted = false;
        for (size_t index = 0; index < keys.size(); ++index) {
            if (keys[index] != EMPTY) find_or_insert(keys[index], values[index], inserted);
        }
    }

    std::vector<uint64_t> keys_;
    std::vector<uint32_t> values_;
    size_t mask_ = 0;
    size_t size_ = 0;
};

struct ContextKey {
    uint64_t low = 0;
    uint64_t high = 0;
    uint32_t length = 0;

    bool operator==(const ContextKey& other) const {
        return low == other.low && high == other.high && length == other.length;
    }
};

bool pack_context(const uint8_t* bytes, size_t length, ContextKey& key) {
    if (length > 16) return false;
    uint8_t padded[16] = {};
    std::memcpy(padded, bytes, length);
    std::memcpy(&key.low, padded, 8);
    std::memcpy(&key.high, padded + 8, 8);
    key.length = static_cast<uint32_t>(length);
    return true;
}

class ContextMap {
public:
    explicit ContextMap(size_t expected) {
        size_t capacity = 1u << 16;
        while (capacity < expected * 2 + 1) capacity <<= 1;
        keys_.assign(capacity, ContextKey{});
        values_.assign(capacity, NONE);
        mask_ = capacity - 1;
    }

    bool insert(const ContextKey& key, uint32_t value) {
        size_t slot = hash(key) & mask_;
        while (values_[slot] != NONE) {
            if (keys_[slot] == key) return false;
            slot = (slot + 1) & mask_;
        }
        keys_[slot] = key;
        values_[slot] = value;
        return true;
    }

    uint32_t find(const ContextKey& key) const {
        size_t slot = hash(key) & mask_;
        while (values_[slot] != NONE) {
            if (keys_[slot] == key) return values_[slot];
            slot = (slot + 1) & mask_;
        }
        return NONE;
    }

private:
    static uint64_t hash(const ContextKey& key) {
        return mix(key.low ^ mix(key.high ^ mix(key.length)));
    }

    std::vector<ContextKey> keys_;
    std::vector<uint32_t> values_;
    size_t mask_ = 0;
};

class Output {
public:
    ~Output() { close(); }

    int open(const char* path, int compress_level) {
        descriptor_ = ::open(path, O_WRONLY | O_CREAT | O_EXCL, 0644);
        if (descriptor_ < 0) return OPEN_FAILED;
        if (compress_level > 0) {
            char mode[4] = {'w', 'b', static_cast<char>('0' + compress_level), 0};
            gz_ = gzdopen(descriptor_, mode);
            if (gz_ == nullptr) return OPEN_FAILED;
            descriptor_ = -1;
            if (gzbuffer(gz_, 1u << 20) != 0) return OPEN_FAILED;
        }
        buffer_.reserve(1u << 22);
        return OK;
    }

    void put(const char* data, size_t length) {
        buffer_.append(data, length);
        bytes_ += length;
    }

    void put(char value) {
        buffer_.push_back(value);
        ++bytes_;
    }

    void put_integer(uint64_t value) {
        char digits[24];
        int length = 0;
        do {
            digits[length++] = static_cast<char>('0' + value % 10);
            value /= 10;
        } while (value);
        while (length) put(digits[--length]);
    }

    int maybe_flush() { return buffer_.size() >= (1u << 22) ? flush() : OK; }

    int flush() {
        size_t offset = 0;
        while (offset < buffer_.size()) {
            size_t remaining = buffer_.size() - offset;
            if (gz_ != nullptr) {
                unsigned part = static_cast<unsigned>(remaining > (1u << 30) ? (1u << 30) : remaining);
                int written = gzwrite(gz_, buffer_.data() + offset, part);
                if (written <= 0) return WRITE_FAILED;
                offset += static_cast<size_t>(written);
            } else {
                ssize_t written = ::write(descriptor_, buffer_.data() + offset, remaining);
                if (written < 0 && errno == EINTR) continue;
                if (written <= 0) return WRITE_FAILED;
                offset += static_cast<size_t>(written);
            }
        }
        buffer_.clear();
        return OK;
    }

    int finish() {
        int status = flush();
        int closed = close();
        return status != OK ? status : closed;
    }

    uint64_t bytes() const { return bytes_; }

private:
    int close() {
        int status = OK;
        if (gz_ != nullptr) {
            if (gzclose(gz_) != Z_OK) status = WRITE_FAILED;
            gz_ = nullptr;
        }
        if (descriptor_ >= 0) {
            if (::close(descriptor_) != 0) status = WRITE_FAILED;
            descriptor_ = -1;
        }
        return status;
    }

    int descriptor_ = -1;
    gzFile gz_ = nullptr;
    std::string buffer_;
    uint64_t bytes_ = 0;
};

class BlockBuilder {
public:
    BlockBuilder(int max_context, int vocab_size, int eos_id, int pad_id)
        : max_context_(max_context), vocab_size_(vocab_size), eos_id_(eos_id), pad_id_(pad_id) {
        add_context(NONE, 0);
    }

    int add_document(const uint8_t* text, uint64_t length, int bos_id, int byte_offset) {
        history_length_ = 0;
        int status = observe(bos_id);
        for (uint64_t index = 0; status == OK && index < length; ++index) status = observe(text[index] + byte_offset);
        return status;
    }

    int write(Output& output, const char* header, size_t header_length) {
        static const char hex[] = "0123456789abcdef";
        output.put(header, header_length);
        for (uint32_t context = 0; context < parent_.size(); ++context) {
            if (head_[context] == NONE) continue;
            output.put("[\"", 2);
            for (uint32_t node = context; node != 0; node = parent_[node]) {
                uint16_t token = token_[node];
                uint8_t bytes[2] = {static_cast<uint8_t>(token & 0xff), static_cast<uint8_t>(token >> 8)};
                for (uint8_t value : bytes) {
                    output.put(hex[value >> 4]);
                    output.put(hex[value & 15]);
                }
            }
            output.put("\",[", 3);
            bool first = true;
            for (uint32_t edge = head_[context]; edge != NONE; edge = edge_next_[edge]) {
                if (!first) output.put(',');
                first = false;
                output.put('[');
                output.put_integer(edge_token_[edge]);
                output.put(',');
                output.put_integer(edge_count_[edge]);
                output.put(']');
            }
            output.put("]]\n", 3);
            int status = output.maybe_flush();
            if (status != OK) return status;
        }
        return OK;
    }

    uint64_t contexts() const {
        uint64_t total = 0;
        for (uint32_t head : head_) total += head != NONE;
        return total;
    }

    uint64_t edges() const { return edge_token_.size(); }

private:
    int observe(int token) {
        if (token < 0 || token >= vocab_size_ || token == pad_id_) return INVALID_TOKEN;
        uint16_t value = static_cast<uint16_t>(token);
        uint32_t context = 0;
        int status = count(context, value);
        int available = history_length_ < max_context_ ? history_length_ : max_context_;
        for (int length = 1; status == OK && length <= available; ++length) {
            context = child(context, history_[history_length_ - length]);
            if (context == NONE) return OVERFLOW;
            status = count(context, value);
        }
        if (status != OK) return status;
        if (max_context_ > 0) {
            if (history_length_ == max_context_) {
                std::memmove(history_, history_ + 1, sizeof(uint16_t) * (max_context_ - 1));
                history_[max_context_ - 1] = value;
            } else {
                history_[history_length_++] = value;
            }
        }
        if (token == eos_id_) history_length_ = 0;
        return OK;
    }

    uint32_t add_context(uint32_t parent, uint16_t token) {
        if (parent_.size() >= NONE - 1) return NONE;
        uint32_t context = static_cast<uint32_t>(parent_.size());
        parent_.push_back(parent);
        token_.push_back(token);
        head_.push_back(NONE);
        tail_.push_back(NONE);
        return context;
    }

    uint32_t child(uint32_t context, uint16_t older) {
        bool inserted = false;
        uint64_t key = (static_cast<uint64_t>(context) << 17) | older;
        uint32_t candidate = static_cast<uint32_t>(parent_.size());
        uint32_t found = map_.find_or_insert(key, candidate, inserted);
        if (inserted && add_context(context, older) != candidate) return NONE;
        return found;
    }

    int count(uint32_t context, uint16_t token) {
        if (edge_token_.size() >= NONE - 1) return OVERFLOW;
        bool inserted = false;
        uint64_t key = (static_cast<uint64_t>(context) << 17) | (1u << 16) | token;
        uint32_t candidate = static_cast<uint32_t>(edge_token_.size());
        uint32_t edge = map_.find_or_insert(key, candidate, inserted);
        if (!inserted) {
            if (edge_count_[edge] == 0xffffffffu) return OVERFLOW;
            ++edge_count_[edge];
            return OK;
        }
        edge_token_.push_back(token);
        edge_count_.push_back(1);
        edge_next_.push_back(NONE);
        if (head_[context] == NONE) {
            head_[context] = edge;
        } else {
            edge_next_[tail_[context]] = edge;
        }
        tail_[context] = edge;
        return OK;
    }

    int max_context_;
    int vocab_size_;
    int eos_id_;
    int pad_id_;
    uint16_t history_[MAX_CONTEXT] = {};
    int history_length_ = 0;
    std::vector<uint32_t> parent_;
    std::vector<uint16_t> token_;
    std::vector<uint32_t> head_;
    std::vector<uint32_t> tail_;
    std::vector<uint16_t> edge_token_;
    std::vector<uint32_t> edge_count_;
    std::vector<uint32_t> edge_next_;
    IndexMap map_;
};

struct Partial {
    std::vector<uint32_t> contexts;
    std::vector<uint32_t> offsets{0};
    std::vector<uint16_t> tokens;
    std::vector<uint64_t> counts;
};

class Projector {
public:
    Projector(const uint8_t* bytes, const uint32_t* lengths, uint64_t count, int vocab_size,
              const char* header, size_t header_length)
        : required_(count), vocab_size_(vocab_size), header_(header, header_length), count_(count),
          rank_(count, NONE), rows_(count) {
        uint64_t offset = 0;
        for (uint64_t index = 0; index < count; ++index) {
            ContextKey key;
            if (lengths[index] % 2 || !pack_context(bytes + offset, lengths[index], key) ||
                !required_.insert(key, static_cast<uint32_t>(index))) {
                valid_ = false;
                return;
            }
            offset += lengths[index];
        }
    }

    bool valid() const { return valid_ && count_ < NONE; }

    int parse(const char* path, Partial& partial) const {
        gzFile file = gzopen(path, "rb");
        if (file == nullptr) return OPEN_FAILED;
        gzbuffer(file, 1u << 20);
        std::string pending;
        std::vector<char> buffer(1u << 22);
        bool header_seen = false;
        int status = OK;
        while (status == OK) {
            int read = gzread(file, buffer.data(), static_cast<unsigned>(buffer.size()));
            if (read < 0) {
                status = READ_FAILED;
                break;
            }
            if (read == 0) break;
            pending.append(buffer.data(), static_cast<size_t>(read));
            size_t start = 0;
            while (status == OK) {
                size_t end = pending.find('\n', start);
                if (end == std::string::npos) break;
                status = header_seen ? parse_line(pending.data() + start, end - start, partial)
                                     : check_header(pending.data() + start, end - start);
                header_seen = true;
                start = end + 1;
            }
            pending.erase(0, start);
        }
        if (status == OK && !pending.empty()) {
            status = header_seen ? parse_line(pending.data(), pending.size(), partial)
                                 : check_header(pending.data(), pending.size());
            header_seen = true;
        }
        if (gzclose(file) != Z_OK && status == OK) status = READ_FAILED;
        if (status == OK && !header_seen) status = HEADER_MISMATCH;
        return status;
    }

    int merge(const Partial& partial) {
        for (size_t row = 0; row < partial.contexts.size(); ++row) {
            uint32_t context = partial.contexts[row];
            if (rank_[context] == NONE) {
                rank_[context] = static_cast<uint32_t>(order_.size());
                order_.push_back(context);
            }
            auto& entries = rows_[context];
            for (uint32_t edge = partial.offsets[row]; edge < partial.offsets[row + 1]; ++edge) {
                int status = add(entries, partial.tokens[edge], partial.counts[edge]);
                if (status != OK) return status;
            }
        }
        return OK;
    }

    int seed(const uint8_t* bytes, const uint32_t* lengths, uint64_t count, const uint32_t* row_lengths,
             const uint16_t* tokens, const uint64_t* counts, uint64_t* skipped) {
        if (!order_.empty()) return STATE_FAILED;
        uint64_t byte_offset = 0;
        uint64_t edge = 0;
        *skipped = 0;
        for (uint64_t row = 0; row < count; ++row) {
            ContextKey key;
            if (lengths[row] % 2 || !pack_context(bytes + byte_offset, lengths[row], key)) return PARSE_FAILED;
            byte_offset += lengths[row];
            uint32_t context = required_.find(key);
            if (context == NONE) {
                ++*skipped;
                edge += row_lengths[row];
                continue;
            }
            if (rank_[context] != NONE) return STATE_FAILED;
            rank_[context] = static_cast<uint32_t>(order_.size());
            order_.push_back(context);
            for (uint32_t index = 0; index < row_lengths[row]; ++index, ++edge) {
                if (tokens[edge] >= vocab_size_ || counts[edge] == 0) return INVALID_TOKEN;
                int status = add(rows_[context], tokens[edge], counts[edge]);
                if (status != OK) return status;
            }
        }
        return OK;
    }

    void sizes(uint64_t* contexts, uint64_t* edges) const {
        *contexts = order_.size();
        *edges = 0;
        for (uint32_t context : order_) *edges += rows_[context].size();
    }

    void export_rows(uint32_t* order, uint32_t* row_lengths, uint16_t* tokens, uint64_t* counts) const {
        uint64_t edge = 0;
        for (size_t row = 0; row < order_.size(); ++row) {
            uint32_t context = order_[row];
            order[row] = context;
            row_lengths[row] = static_cast<uint32_t>(rows_[context].size());
            for (const auto& entry : rows_[context]) {
                tokens[edge] = entry.first;
                counts[edge] = entry.second;
                ++edge;
            }
        }
    }

private:
    static int add(std::vector<std::pair<uint16_t, uint64_t>>& entries, uint16_t token, uint64_t count) {
        for (auto& entry : entries) {
            if (entry.first == token) {
                if (entry.second > ~0ULL - count) return OVERFLOW;
                entry.second += count;
                return OK;
            }
        }
        entries.emplace_back(token, count);
        return OK;
    }

    int check_header(const char* line, size_t length) const {
        return length == header_.size() && std::memcmp(line, header_.data(), length) == 0 ? OK : HEADER_MISMATCH;
    }

    static int hex_value(char value) {
        if (value >= '0' && value <= '9') return value - '0';
        if (value >= 'a' && value <= 'f') return value - 'a' + 10;
        if (value >= 'A' && value <= 'F') return value - 'A' + 10;
        return -1;
    }

    static bool read_integer(const char*& cursor, const char* end, uint64_t& value) {
        if (cursor == end || *cursor < '0' || *cursor > '9') return false;
        value = 0;
        while (cursor < end && *cursor >= '0' && *cursor <= '9') {
            uint64_t digit = static_cast<uint64_t>(*cursor - '0');
            if (value > (~0ULL - digit) / 10) return false;
            value = value * 10 + digit;
            ++cursor;
        }
        return true;
    }

    int parse_line(const char* line, size_t length, Partial& partial) const {
        const char* cursor = line;
        const char* end = line + length;
        if (length < 7 || cursor[0] != '[' || cursor[1] != '"') return PARSE_FAILED;
        cursor += 2;
        const char* hex_start = cursor;
        while (cursor < end && *cursor != '"') ++cursor;
        if (cursor == end) return PARSE_FAILED;
        size_t hex_length = static_cast<size_t>(cursor - hex_start);
        if (hex_length % 2) return PARSE_FAILED;
        uint8_t bytes[16];
        bool candidate = hex_length <= 32;
        for (size_t index = 0; index < hex_length; index += 2) {
            int high = hex_value(hex_start[index]);
            int low = hex_value(hex_start[index + 1]);
            if (high < 0 || low < 0) return PARSE_FAILED;
            if (candidate) bytes[index / 2] = static_cast<uint8_t>(high * 16 + low);
        }
        uint32_t context = NONE;
        if (candidate) {
            ContextKey key;
            pack_context(bytes, hex_length / 2, key);
            context = required_.find(key);
        }
        if (context == NONE) return OK;
        ++cursor;
        if (end - cursor < 3 || cursor[0] != ',' || cursor[1] != '[') return PARSE_FAILED;
        cursor += 2;
        partial.contexts.push_back(context);
        bool first = true;
        while (cursor < end && *cursor != ']') {
            if (!first) {
                if (*cursor != ',') return PARSE_FAILED;
                ++cursor;
            }
            first = false;
            uint64_t token = 0;
            uint64_t count = 0;
            if (cursor == end || *cursor++ != '[' || !read_integer(cursor, end, token) || cursor == end ||
                *cursor++ != ',' || !read_integer(cursor, end, count) || cursor == end || *cursor++ != ']') {
                return PARSE_FAILED;
            }
            if (token >= static_cast<uint64_t>(vocab_size_) || count == 0) return INVALID_TOKEN;
            partial.tokens.push_back(static_cast<uint16_t>(token));
            partial.counts.push_back(count);
        }
        if (end - cursor != 2 || cursor[0] != ']' || cursor[1] != ']') return PARSE_FAILED;
        if (partial.tokens.size() >= NONE) return OVERFLOW;
        partial.offsets.push_back(static_cast<uint32_t>(partial.tokens.size()));
        return OK;
    }

    ContextMap required_;
    int vocab_size_;
    std::string header_;
    bool valid_ = true;
    uint64_t count_ = 0;
    std::vector<uint32_t> rank_;
    std::vector<uint32_t> order_;
    std::vector<std::vector<std::pair<uint16_t, uint64_t>>> rows_;
};

}  // namespace

extern "C" {

int blt_count_block(const uint8_t* text, const uint64_t* lengths, uint64_t documents, int max_context,
                    int vocab_size, int eos_id, int pad_id, int bos_id, int byte_offset, const char* header,
                    uint64_t header_length, const char* path, int compress_level, uint64_t* stats) {
    if (max_context < 0 || max_context > MAX_CONTEXT || vocab_size < 2 || vocab_size > 65536 ||
        compress_level < 0 || compress_level > 9 || stats == nullptr) {
        return INVALID_ARGUMENT;
    }
    try {
        BlockBuilder builder(max_context, vocab_size, eos_id, pad_id);
        uint64_t offset = 0;
        for (uint64_t document = 0; document < documents; ++document) {
            int status = builder.add_document(text + offset, lengths[document], bos_id, byte_offset);
            if (status != OK) return status;
            offset += lengths[document];
        }
        Output output;
        int status = output.open(path, compress_level);
        if (status == OK) status = builder.write(output, header, header_length);
        int finished = output.finish();
        if (status != OK) return status;
        if (finished != OK) return finished;
        stats[0] = builder.contexts();
        stats[1] = builder.edges();
        stats[2] = output.bytes();
        return OK;
    } catch (const std::bad_alloc&) {
        return OUT_OF_MEMORY;
    }
}

void* blt_projector_new(const uint8_t* bytes, const uint32_t* lengths, uint64_t count, int vocab_size,
                        const char* header, uint64_t header_length) {
    try {
        auto* projector = new Projector(bytes, lengths, count, vocab_size, header, header_length);
        if (!projector->valid()) {
            delete projector;
            return nullptr;
        }
        return projector;
    } catch (const std::bad_alloc&) {
        return nullptr;
    }
}

void blt_projector_free(void* projector) { delete static_cast<Projector*>(projector); }

void* blt_projector_parse(const void* projector, const char* path, int* status) {
    try {
        auto* partial = new Partial();
        *status = static_cast<const Projector*>(projector)->parse(path, *partial);
        if (*status != OK) {
            delete partial;
            return nullptr;
        }
        return partial;
    } catch (const std::bad_alloc&) {
        *status = OUT_OF_MEMORY;
        return nullptr;
    }
}

void blt_partial_free(void* partial) { delete static_cast<Partial*>(partial); }

int blt_projector_merge(void* projector, const void* partial) {
    try {
        return static_cast<Projector*>(projector)->merge(*static_cast<const Partial*>(partial));
    } catch (const std::bad_alloc&) {
        return OUT_OF_MEMORY;
    }
}

int blt_projector_seed(void* projector, const uint8_t* bytes, const uint32_t* lengths, uint64_t count,
                       const uint32_t* row_lengths, const uint16_t* tokens, const uint64_t* counts,
                       uint64_t* skipped) {
    try {
        return static_cast<Projector*>(projector)->seed(bytes, lengths, count, row_lengths, tokens, counts, skipped);
    } catch (const std::bad_alloc&) {
        return OUT_OF_MEMORY;
    }
}

void blt_projector_sizes(const void* projector, uint64_t* contexts, uint64_t* edges) {
    static_cast<const Projector*>(projector)->sizes(contexts, edges);
}

void blt_projector_export(const void* projector, uint32_t* order, uint32_t* row_lengths, uint16_t* tokens,
                          uint64_t* counts) {
    static_cast<const Projector*>(projector)->export_rows(order, row_lengths, tokens, counts);
}

}
