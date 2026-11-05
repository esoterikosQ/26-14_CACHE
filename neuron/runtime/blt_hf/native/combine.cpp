// Native core for blt_hf.entropy_combine (C++11, no external libraries).
// unicode_tables.inc is generated at build time from the running Python's unicodedata.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "unicode_tables.inc"

namespace {

const uint64_t MAX_RECORD_BYTES = 16ull * 1024 * 1024;
const size_t RECORD = 128;  // exact[32] idd[32] normd[32] text_bytes u64 line_offset u64 line_length u32 flags u8
const uint8_t QUARANTINE = 1, FALLBACK = 2;
const uint32_t NONE = 0xFFFFFFFFu;  // glibc < 2.18 hides UINT32_MAX from C++ without __STDC_LIMIT_MACROS

const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};

inline uint32_t rotr(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }

struct Sha256 {
    uint32_t h[8];
    uint8_t buffer[64];
    uint64_t length;
    size_t fill;
    Sha256() {
        const uint32_t initial[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                                     0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
        std::memcpy(h, initial, sizeof(h));
        length = 0;
        fill = 0;
    }
    void block(const uint8_t* p) {
        uint32_t w[64];
        for (int i = 0; i < 16; ++i)
            w[i] = (uint32_t(p[4 * i]) << 24) | (uint32_t(p[4 * i + 1]) << 16) | (uint32_t(p[4 * i + 2]) << 8) | p[4 * i + 3];
        for (int i = 16; i < 64; ++i) {
            uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
            uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16] + s0 + w[i - 7] + s1;
        }
        uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], k = h[7];
        for (int i = 0; i < 64; ++i) {
            uint32_t t1 = k + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
            uint32_t t2 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
            k = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
        }
        h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += k;
    }
    void update(const uint8_t* p, size_t n) {
        length += n;
        if (fill) {
            size_t take = std::min(n, 64 - fill);
            std::memcpy(buffer + fill, p, take);
            fill += take; p += take; n -= take;
            if (fill < 64) return;
            block(buffer);
            fill = 0;
        }
        for (; n >= 64; p += 64, n -= 64) block(p);
        std::memcpy(buffer, p, n);
        fill = n;
    }
    void finish(uint8_t* out) {
        uint64_t bits = length * 8;
        uint8_t pad = 0x80;
        update(&pad, 1);
        uint8_t zero = 0;
        while (fill != 56) update(&zero, 1);
        uint8_t size[8];
        for (int i = 0; i < 8; ++i) size[i] = uint8_t(bits >> (56 - 8 * i));
        update(size, 8);
        for (int i = 0; i < 8; ++i) {
            out[4 * i] = uint8_t(h[i] >> 24); out[4 * i + 1] = uint8_t(h[i] >> 16);
            out[4 * i + 2] = uint8_t(h[i] >> 8); out[4 * i + 3] = uint8_t(h[i]);
        }
    }
};

void sha256(const void* data, size_t size, uint8_t* out) {
    Sha256 state;
    state.update(static_cast<const uint8_t*>(data), size);
    state.finish(out);
}

struct Tables {
    uint8_t bmp[65536];  // bit 1: Python str.isspace, bit 2: not provably NFC-stable
    Tables() {
        std::memset(bmp, 0, sizeof(bmp));
        for (size_t i = 0; i < sizeof(WHITESPACE) / sizeof(WHITESPACE[0]); ++i)
            if (WHITESPACE[i] < 65536) bmp[WHITESPACE[i]] |= 1;
        for (size_t i = 0; i < sizeof(UNSAFE) / sizeof(UNSAFE[0]); ++i)
            for (uint32_t c = UNSAFE[i][0]; c <= UNSAFE[i][1] && c < 65536; ++c) bmp[c] |= 2;
    }
};
const Tables TABLES;

bool is_space(uint32_t c) {
    if (c < 65536) return TABLES.bmp[c] & 1;
    for (size_t i = 0; i < sizeof(WHITESPACE) / sizeof(WHITESPACE[0]); ++i)
        if (WHITESPACE[i] == c) return true;
    return false;
}

bool is_unsafe(uint32_t c) {
    if (c < 65536) return TABLES.bmp[c] & 2;
    size_t low = 0, high = sizeof(UNSAFE) / sizeof(UNSAFE[0]);
    while (low < high) {
        size_t middle = (low + high) / 2;
        if (UNSAFE[middle][1] < c) low = middle + 1;
        else high = middle;
    }
    return low < sizeof(UNSAFE) / sizeof(UNSAFE[0]) && UNSAFE[low][0] <= c;
}

void fail(char* error, uint64_t size, const std::string& message) {
    if (size) {
        size_t n = std::min<size_t>(message.size(), size - 1);
        std::memcpy(error, message.data(), n);
        error[n] = 0;
    }
}

// Strict UTF-8 as Python bytes.decode('utf-8'): no overlongs, surrogates or code points above U+10FFFF.
bool valid_utf8(const uint8_t* p, size_t n) {
    size_t i = 0;
    while (i < n) {
        uint8_t c = p[i];
        if (c < 0x80) { ++i; continue; }
        size_t need;
        uint32_t low = 0x80, high = 0xBF;
        if (c >= 0xC2 && c <= 0xDF) need = 1;
        else if (c >= 0xE0 && c <= 0xEF) { need = 2; if (c == 0xE0) low = 0xA0; if (c == 0xED) high = 0x9F; }
        else if (c >= 0xF0 && c <= 0xF4) { need = 3; if (c == 0xF0) low = 0x90; if (c == 0xF4) high = 0x8F; }
        else return false;
        if (i + need >= n) return false;
        if (p[i + 1] < low || p[i + 1] > high) return false;
        for (size_t k = 2; k <= need; ++k)
            if (p[i + k] < 0x80 || p[i + k] > 0xBF) return false;
        i += need + 1;
    }
    return true;
}

uint32_t next_code_point(const std::string& s, size_t& i) {
    uint8_t c = uint8_t(s[i]);
    if (c < 0x80) { ++i; return c; }
    if (c < 0xE0) { uint32_t v = ((c & 0x1F) << 6) | (uint8_t(s[i + 1]) & 0x3F); i += 2; return v; }
    if (c < 0xF0) {
        uint32_t v = ((c & 0x0F) << 12) | ((uint8_t(s[i + 1]) & 0x3F) << 6) | (uint8_t(s[i + 2]) & 0x3F);
        i += 3;
        return v;
    }
    uint32_t v = ((c & 0x07) << 18) | ((uint8_t(s[i + 1]) & 0x3F) << 12) | ((uint8_t(s[i + 2]) & 0x3F) << 6) |
                 (uint8_t(s[i + 3]) & 0x3F);
    i += 4;
    return v;
}

void append_utf8(std::string& out, uint32_t c) {
    if (c < 0x80) out += char(c);
    else if (c < 0x800) { out += char(0xC0 | (c >> 6)); out += char(0x80 | (c & 0x3F)); }
    else if (c < 0x10000) {
        out += char(0xE0 | (c >> 12)); out += char(0x80 | ((c >> 6) & 0x3F)); out += char(0x80 | (c & 0x3F));
    } else {
        out += char(0xF0 | (c >> 18)); out += char(0x80 | ((c >> 12) & 0x3F));
        out += char(0x80 | ((c >> 6) & 0x3F)); out += char(0x80 | (c & 0x3F));
    }
}

struct Row {
    std::string id, source, text;
};

void skip_space(const char*& p, const char* end) {
    while (p < end && (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')) ++p;
}

int hex_value(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

bool read_hex4(const char*& p, const char* end, uint32_t& value) {
    if (end - p < 4) return false;
    value = 0;
    for (int i = 0; i < 4; ++i) {
        int digit = hex_value(p[i]);
        if (digit < 0) return false;
        value = value * 16 + uint32_t(digit);
    }
    p += 4;
    return true;
}

// Python json.loads string rules (strict=True); lone surrogates are rejected because they cannot be UTF-8 encoded.
const char* parse_string(const char*& p, const char* end, std::string& out) {
    if (p >= end || *p != '"') return "Invalid id/source/text record";
    ++p;
    out.clear();
    while (p < end) {
        const char* run = p;
        while (p < end && *p != '"' && *p != '\\' && uint8_t(*p) >= 0x20) ++p;
        out.append(run, size_t(p - run));
        if (p >= end) break;
        uint8_t c = uint8_t(*p);
        if (c == '"') { ++p; return 0; }
        if (c < 0x20) return "Invalid control character in JSONL record";
        if (++p >= end) return "Invalid JSON escape";
        char e = *p++;
        switch (e) {
            case '"': out += '"'; break;
            case '\\': out += '\\'; break;
            case '/': out += '/'; break;
            case 'b': out += '\b'; break;
            case 'f': out += '\f'; break;
            case 'n': out += '\n'; break;
            case 'r': out += '\r'; break;
            case 't': out += '\t'; break;
            case 'u': {
                uint32_t value;
                if (!read_hex4(p, end, value)) return "Invalid JSON escape";
                if (value >= 0xD800 && value <= 0xDBFF) {
                    uint32_t low;
                    if (end - p >= 6 && p[0] == '\\' && p[1] == 'u') {
                        const char* q = p + 2;
                        if (read_hex4(q, end, low) && low >= 0xDC00 && low <= 0xDFFF) {
                            p = q;
                            value = 0x10000 + ((value - 0xD800) << 10) + (low - 0xDC00);
                        } else return "Lone surrogate in JSONL record";
                    } else return "Lone surrogate in JSONL record";
                } else if (value >= 0xDC00 && value <= 0xDFFF) return "Lone surrogate in JSONL record";
                append_utf8(out, value);
                break;
            }
            default: return "Invalid JSON escape";
        }
    }
    return "Unterminated JSON string";
}

// Accepts exactly one flat object whose keys are id/source/text with string values (fail-closed on anything else).
const char* parse_row(const char* p, const char* end, Row& row) {
    if (!valid_utf8(reinterpret_cast<const uint8_t*>(p), size_t(end - p))) return "JSONL record is not valid UTF-8";
    bool seen[3] = {false, false, false};
    std::string key, value;
    skip_space(p, end);
    if (p >= end || *p != '{') return "Invalid id/source/text record";
    ++p;
    skip_space(p, end);
    if (p < end && *p == '}') return "Invalid id/source/text record";
    while (true) {
        skip_space(p, end);
        const char* message = parse_string(p, end, key);
        if (message) return message;
        skip_space(p, end);
        if (p >= end || *p != ':') return "Invalid id/source/text record";
        ++p;
        skip_space(p, end);
        message = parse_string(p, end, value);
        if (message) return message;
        int slot = key == "id" ? 0 : key == "source" ? 1 : key == "text" ? 2 : -1;
        if (slot < 0) return "Unexpected JSONL record key";
        (slot == 0 ? row.id : slot == 1 ? row.source : row.text).swap(value);
        seen[slot] = true;
        skip_space(p, end);
        if (p < end && *p == ',') { ++p; continue; }
        if (p < end && *p == '}') { ++p; break; }
        return "Invalid id/source/text record";
    }
    skip_space(p, end);
    if (p != end || !seen[0] || !seen[1] || !seen[2] || row.id.empty() || row.source.empty())
        return "Invalid id/source/text record";
    return 0;
}

// Python json.dumps(..., ensure_ascii=False) string encoding.
void escape(const std::string& s, std::string& out) {
    static const char digits[] = "0123456789abcdef";
    out += '"';
    size_t run = 0;
    for (size_t i = 0; i < s.size(); ++i) {
        uint8_t c = uint8_t(s[i]);
        if (c >= 0x20 && c != '"' && c != '\\') continue;
        out.append(s, run, i - run);
        run = i + 1;
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            case '\b': out += "\\b"; break;
            case '\f': out += "\\f"; break;
            default:
                out += "\\u00"; out += digits[c >> 4]; out += digits[c & 15];
        }
    }
    out.append(s, run, s.size() - run);
    out += '"';
}

void encode(const Row& row, std::string& out) {
    out.assign("{\"id\": ");
    escape(row.id, out);
    out += ", \"source\": ";
    escape(row.source, out);
    out += ", \"text\": ";
    escape(row.text, out);
    out += "}\n";
}

// Returns false when the text needs Python NFC; otherwise writes ' '.join(text.split()).
bool collapse(const std::string& text, std::string& out) {
    out.clear();
    bool pending = false;
    size_t i = 0;
    while (i < text.size()) {
        size_t start = i;
        uint32_t c = next_code_point(text, i);
        if (is_unsafe(c)) return false;
        if (is_space(c)) { pending = !out.empty(); continue; }
        if (pending) { out += ' '; pending = false; }
        out.append(text, start, i - start);
    }
    return true;
}

// Finds the next line in [data+pos, data+size); returns 1 for a line, 0 when more data is needed, -1 on error.
int next_line(const char* data, uint64_t size, uint64_t pos, int final, uint64_t& length, uint64_t& next,
              char* error, uint64_t error_size) {
    if (pos >= size) return 0;
    const void* newline = std::memchr(data + pos, '\n', size_t(size - pos));
    if (!newline) {
        // Python readline(MAX+1) fails once an unterminated record exceeds MAX bytes.
        if (size - pos > MAX_RECORD_BYTES) { fail(error, error_size, "JSONL record exceeds16MiB"); return -1; }
        if (!final) return 0;
        length = size - pos;
        next = size;
        return 1;
    }
    uint64_t end = uint64_t(static_cast<const char*>(newline) - data);
    if (end + 1 - pos > MAX_RECORD_BYTES) { fail(error, error_size, "JSONL record exceeds16MiB"); return -1; }
    length = end - pos;
    next = end + 1;
    return 1;
}

uint64_t prefix(const uint8_t* p) {
    uint64_t v = 0;
    for (int i = 0; i < 8; ++i) v = (v << 8) | p[i];
    return v;
}

uint32_t find(std::vector<uint32_t>& parent, uint32_t x) {
    while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; }
    return x;
}

void unite(std::vector<uint32_t>& parent, uint32_t a, uint32_t b) {
    a = find(parent, a); b = find(parent, b);
    if (a != b) parent[std::max(a, b)] = std::min(a, b);
}

struct Buckets {
    FILE* files[256];
};

}  // namespace

extern "C" {

const char* bltc_unicode_version() { return UNICODE_VERSION; }

int bltc_hash_text(const char* data, uint64_t size, uint8_t* exact, uint8_t* normalized, int* state) {
    std::string text(data, size_t(size)), collapsed;
    sha256(text.data(), text.size(), exact);
    if (!collapse(text, collapsed)) { *state = FALLBACK; return 0; }
    if (collapsed.empty()) { *state = QUARANTINE; return 0; }
    sha256(collapsed.data(), collapsed.size(), normalized);
    *state = 0;
    return 0;
}

int bltc_roundtrip(const char* data, uint64_t size, char* output, uint64_t capacity, uint64_t* written,
                   char* error, uint64_t error_size) {
    Row row;
    const char* message = parse_row(data, data + size, row);
    if (message) { fail(error, error_size, message); return 1; }
    std::string line;
    encode(row, line);
    if (line.size() > capacity) { fail(error, error_size, "Output buffer too small"); return 1; }
    std::memcpy(output, line.data(), line.size());
    *written = line.size();
    return 0;
}

int bltc_scan(const char* data, uint64_t size, int final, const char* expected_source, uint64_t source_length,
              uint8_t* records, uint64_t capacity, uint64_t* count, uint64_t* consumed, char* error, uint64_t error_size) {
    uint64_t pos = 0, n = 0, length = 0, next = 0;
    Row row;
    std::string collapsed;
    while (n < capacity) {
        int found = next_line(data, size, pos, final, length, next, error, error_size);
        if (found < 0) return 1;
        if (!found) break;
        const char* message = parse_row(data + pos, data + pos + length, row);
        if (message) { fail(error, error_size, message); return 1; }
        if (expected_source && (row.source.size() != source_length || std::memcmp(row.source.data(), expected_source, size_t(source_length))))
            { fail(error, error_size, "FineWeb source changed"); return 1; }
        uint8_t* record = records + n * RECORD;
        std::memset(record, 0, RECORD);
        sha256(row.text.data(), row.text.size(), record);
        sha256(row.id.data(), row.id.size(), record + 32);
        uint8_t flags = 0;
        if (!collapse(row.text, collapsed)) flags = FALLBACK;
        else if (collapsed.empty()) flags = QUARANTINE;
        else sha256(collapsed.data(), collapsed.size(), record + 64);
        uint64_t text_bytes = row.text.size();
        uint32_t line_length = uint32_t(length);
        std::memcpy(record + 96, &text_bytes, 8);
        std::memcpy(record + 104, &pos, 8);
        std::memcpy(record + 112, &line_length, 4);
        record[116] = flags;
        ++n;
        pos = next;
    }
    *count = n;
    *consumed = pos;
    return 0;
}

int bltc_group(const uint8_t* fineweb, uint64_t fineweb_count,
               const uint8_t* nikl_exact, const uint8_t* nikl_role, const int64_t* nikl_group, uint64_t nikl_count,
               uint64_t nikl_groups, const uint8_t* token_kind, const uint8_t* token_value, const int64_t* token_owner,
               uint64_t token_count, const char* seed_prefix, uint64_t seed_length, double validation_percent,
               double test_percent, uint8_t* fineweb_split, uint8_t* nikl_split, uint64_t* stats,
               char* error, uint64_t error_size) {
    // Same (source, id) must keep one body; every FineWeb record shares SOURCE, including quarantined ones.
    {
        std::vector<uint32_t> order(fineweb_count);
        for (uint64_t i = 0; i < fineweb_count; ++i) order[i] = uint32_t(i);
        std::sort(order.begin(), order.end(), [&](uint32_t a, uint32_t b) {
            int c = std::memcmp(fineweb + a * RECORD + 32, fineweb + b * RECORD + 32, 32);
            return c < 0 || (c == 0 && a < b);
        });
        for (uint64_t i = 1; i < fineweb_count; ++i) {
            const uint8_t* a = fineweb + uint64_t(order[i - 1]) * RECORD;
            const uint8_t* b = fineweb + uint64_t(order[i]) * RECORD;
            if (!std::memcmp(a + 32, b + 32, 32) && std::memcmp(a, b, 32))
                { fail(error, error_size, "Conflicting FineWeb document identity"); return 1; }
        }
    }
    std::vector<uint32_t> node_record;
    std::vector<uint32_t> record_node(fineweb_count, NONE);
    for (uint64_t i = 0; i < fineweb_count; ++i) {
        uint8_t flags = fineweb[i * RECORD + 116];
        if (flags & FALLBACK) { fail(error, error_size, "Unresolved NFC fallback record"); return 1; }
        if (!(flags & QUARANTINE)) { record_node[i] = uint32_t(nikl_count + node_record.size()); node_record.push_back(uint32_t(i)); }
    }
    uint64_t total = nikl_count + node_record.size();
    if (total >= NONE || fineweb_count >= NONE) { fail(error, error_size, "Too many documents for 32-bit nodes"); return 1; }
    std::vector<const uint8_t*> exact(total);
    for (uint64_t i = 0; i < nikl_count; ++i) exact[i] = nikl_exact + 32 * i;
    for (uint64_t i = 0; i < node_record.size(); ++i) exact[nikl_count + i] = fineweb + uint64_t(node_record[i]) * RECORD;
    std::vector<uint32_t> parent(total);
    for (uint64_t i = 0; i < total; ++i) parent[i] = uint32_t(i);
    std::vector<uint32_t> first(nikl_groups, NONE);
    for (uint64_t i = 0; i < nikl_count; ++i) {
        if (nikl_group[i] < 0 || uint64_t(nikl_group[i]) >= nikl_groups) { fail(error, error_size, "Invalid NIKL group index"); return 1; }
        uint32_t& head = first[size_t(nikl_group[i])];
        if (head == NONE) head = uint32_t(i);
        else unite(parent, uint32_t(i), head);
    }
    {
        struct Token { uint64_t key; const uint8_t* value; uint32_t node; uint8_t kind; };
        std::vector<Token> tokens;
        tokens.reserve(size_t(token_count + 2 * node_record.size()));
        for (uint64_t i = 0; i < token_count; ++i) {
            if (token_owner[i] < 0 || uint64_t(token_owner[i]) >= nikl_count || token_kind[i] > 1)
                { fail(error, error_size, "Invalid NIKL link"); return 1; }
            Token t = {prefix(token_value + 32 * i), token_value + 32 * i, uint32_t(token_owner[i]), token_kind[i]};
            tokens.push_back(t);
        }
        for (uint64_t i = 0; i < node_record.size(); ++i) {
            const uint8_t* record = fineweb + uint64_t(node_record[i]) * RECORD;
            Token id = {prefix(record + 32), record + 32, uint32_t(nikl_count + i), 0};
            Token normalized = {prefix(record + 64), record + 64, uint32_t(nikl_count + i), 1};
            tokens.push_back(id);
            tokens.push_back(normalized);
        }
        std::sort(tokens.begin(), tokens.end(), [](const Token& a, const Token& b) {
            if (a.kind != b.kind) return a.kind < b.kind;
            if (a.key != b.key) return a.key < b.key;
            int c = std::memcmp(a.value, b.value, 32);
            return c < 0 || (c == 0 && a.node < b.node);
        });
        for (size_t i = 1; i < tokens.size(); ++i)
            if (tokens[i].kind == tokens[i - 1].kind && tokens[i].key == tokens[i - 1].key &&
                !std::memcmp(tokens[i].value, tokens[i - 1].value, 32))
                unite(parent, tokens[i].node, tokens[i - 1].node);
    }
    std::vector<uint8_t> role(total, 255);
    for (uint64_t i = 0; i < nikl_count; ++i) {
        uint32_t root = find(parent, uint32_t(i));
        if (role[root] == 255) role[root] = nikl_role[i];
        else if (role[root] != nikl_role[i])
            { fail(error, error_size, "FineWeb document bridges protected NIKL splits; no reassignment allowed"); return 1; }
    }
    std::vector<uint32_t> key(total, NONE);
    for (uint64_t n = 0; n < total; ++n) {
        uint32_t root = find(parent, uint32_t(n));
        if (key[root] == NONE || std::memcmp(exact[n], exact[key[root]], 32) < 0) key[root] = uint32_t(n);
    }
    std::vector<uint8_t> split(total, 255);
    uint64_t groups[3] = {0, 0, 0};
    static const char digits[] = "0123456789abcdef";
    std::string message(seed_prefix, size_t(seed_length));
    for (uint64_t n = 0; n < total; ++n) {
        if (parent[n] != n) continue;
        uint8_t assigned = role[n];
        if (assigned == 255) {
            message.resize(size_t(seed_length));
            for (int i = 0; i < 32; ++i) { message += digits[exact[key[n]][i] >> 4]; message += digits[exact[key[n]][i] & 15]; }
            uint8_t digest[32];
            sha256(message.data(), message.size(), digest);
            double score = double(prefix(digest)) / 18446744073709551616.0 * 100.0;
            assigned = score < test_percent ? 2 : score < test_percent + validation_percent ? 1 : 0;
        }
        split[n] = assigned;
        ++groups[assigned];
    }
    std::vector<uint64_t> keys(total);
    for (uint64_t n = 0; n < total; ++n) keys[n] = prefix(exact[n]);
    std::vector<uint32_t> order(total);
    for (uint64_t n = 0; n < total; ++n) order[n] = uint32_t(n);
    std::sort(order.begin(), order.end(), [&](uint32_t a, uint32_t b) {
        if (keys[a] != keys[b]) return keys[a] < keys[b];
        int c = std::memcmp(exact[a], exact[b], 32);
        return c < 0 || (c == 0 && a < b);
    });
    std::memset(fineweb_split, 255, size_t(fineweb_count));
    uint64_t unique = 0;
    for (uint64_t i = 0; i < total; ++i) {
        uint32_t n = order[i];
        if (i && keys[order[i - 1]] == keys[n] && !std::memcmp(exact[order[i - 1]], exact[n], 32)) continue;
        ++unique;
        if (n >= nikl_count) fineweb_split[node_record[n - nikl_count]] = split[find(parent, n)];
    }
    for (uint64_t i = 0; i < nikl_count; ++i) nikl_split[i] = split[find(parent, uint32_t(i))];
    stats[0] = groups[0]; stats[1] = groups[1]; stats[2] = groups[2];
    stats[3] = unique; stats[4] = total;
    return 0;
}

void* bltc_bucket_open(const char* prefix_path) {
    Buckets* buckets = new Buckets();
    for (int i = 0; i < 256; ++i) {
        char path[4096];
        std::snprintf(path, sizeof(path), "%s%03d.bin", prefix_path, i);
        buckets->files[i] = std::fopen(path, "wb");
        if (!buckets->files[i]) {
            for (int k = 0; k < i; ++k) std::fclose(buckets->files[k]);
            delete buckets;
            return 0;
        }
    }
    return buckets;
}

int bltc_bucket_close(void* handle) {
    Buckets* buckets = static_cast<Buckets*>(handle);
    int status = 0;
    for (int i = 0; i < 256; ++i) {
        if (std::ferror(buckets->files[i])) status = 1;
        if (std::fclose(buckets->files[i])) status = 1;
    }
    delete buckets;
    return status;
}

// Re-encodes selected lines (split != 255) as Python would and appends them to the bucket of exact[0].
int bltc_bucket_write(void* handle, const char* data, uint64_t size, int final, const uint8_t* splits,
                      const uint8_t* expected_exact, uint64_t lines, uint64_t* done, uint64_t* consumed,
                      char* error, uint64_t error_size) {
    Buckets* buckets = static_cast<Buckets*>(handle);
    uint64_t pos = 0, n = 0, length = 0, next = 0;
    Row row;
    std::string line;
    while (n < lines) {
        int found = next_line(data, size, pos, final, length, next, error, error_size);
        if (found < 0) return 1;
        if (!found) break;
        if (splits[n] != 255) {
            if (splits[n] > 2) { fail(error, error_size, "Invalid split code"); return 1; }
            const char* message = parse_row(data + pos, data + pos + length, row);
            if (message) { fail(error, error_size, message); return 1; }
            uint8_t exact[32];
            sha256(row.text.data(), row.text.size(), exact);
            if (expected_exact && std::memcmp(exact, expected_exact + 32 * n, 32))
                { fail(error, error_size, "FineWeb input changed between passes"); return 1; }
            encode(row, line);
            uint64_t text_bytes = row.text.size();
            uint32_t source_length = uint32_t(row.source.size()), line_length = uint32_t(line.size());
            FILE* file = buckets->files[exact[0]];
            if (std::fwrite(exact, 1, 32, file) != 32 || std::fwrite(&splits[n], 1, 1, file) != 1 ||
                std::fwrite(&text_bytes, 8, 1, file) != 1 || std::fwrite(&source_length, 4, 1, file) != 1 ||
                std::fwrite(&line_length, 4, 1, file) != 1 ||
                std::fwrite(row.source.data(), 1, source_length, file) != source_length ||
                std::fwrite(line.data(), 1, line_length, file) != line_length)
                { fail(error, error_size, "Bucket write failed"); return 1; }
        }
        ++n;
        pos = next;
    }
    *done = n;
    *consumed = pos;
    return 0;
}

// Sorts one bucket by exact SHA-256 and appends lines to the split files; summary is JSON for Python.
int bltc_merge(const char* paths, const char* train, const char* validation, const char* test, char** summary,
               char* error, uint64_t error_size) {
    std::vector<char> data;
    std::string list(paths);
    size_t start = 0;
    while (start <= list.size()) {
        size_t end = list.find('\n', start);
        if (end == std::string::npos) end = list.size();
        if (end > start) {
            std::string path = list.substr(start, end - start);
            FILE* file = std::fopen(path.c_str(), "rb");
            if (!file) { fail(error, error_size, "Cannot open bucket " + path); return 1; }
            std::fseek(file, 0, SEEK_END);
            long size = std::ftell(file);
            std::fseek(file, 0, SEEK_SET);
            size_t offset = data.size();
            data.resize(offset + size_t(size));
            if (size && std::fread(&data[offset], 1, size_t(size), file) != size_t(size))
                { std::fclose(file); fail(error, error_size, "Cannot read bucket " + path); return 1; }
            std::fclose(file);
        }
        start = end + 1;
    }
    std::vector<const char*> entries;
    size_t pos = 0;
    while (pos < data.size()) {
        if (data.size() - pos < 49) { fail(error, error_size, "Truncated bucket entry"); return 1; }
        uint32_t source_length, line_length;
        std::memcpy(&source_length, &data[pos + 41], 4);
        std::memcpy(&line_length, &data[pos + 45], 4);
        if (data.size() - pos < 49 + uint64_t(source_length) + line_length) { fail(error, error_size, "Truncated bucket entry"); return 1; }
        entries.push_back(&data[pos]);
        pos += 49 + size_t(source_length) + line_length;
    }
    std::sort(entries.begin(), entries.end(), [](const char* a, const char* b) { return std::memcmp(a, b, 32) < 0; });
    for (size_t i = 1; i < entries.size(); ++i)
        if (!std::memcmp(entries[i - 1], entries[i], 32)) { fail(error, error_size, "Duplicate exact text in output"); return 1; }
    FILE* outputs[3] = {std::fopen(train, "ab"), std::fopen(validation, "ab"), std::fopen(test, "ab")};
    if (!outputs[0] || !outputs[1] || !outputs[2]) {
        for (int i = 0; i < 3; ++i) if (outputs[i]) std::fclose(outputs[i]);
        fail(error, error_size, "Cannot open split output");
        return 1;
    }
    struct Count { uint8_t split; std::string source; uint64_t documents, bytes; };
    std::vector<Count> counts;
    bool ok = true;
    for (size_t i = 0; i < entries.size() && ok; ++i) {
        const char* entry = entries[i];
        uint8_t split = uint8_t(entry[32]);
        uint64_t text_bytes;
        uint32_t source_length, line_length;
        std::memcpy(&text_bytes, entry + 33, 8);
        std::memcpy(&source_length, entry + 41, 4);
        std::memcpy(&line_length, entry + 45, 4);
        if (split > 2) { ok = false; break; }
        std::string source(entry + 49, source_length);
        ok = std::fwrite(entry + 49 + source_length, 1, line_length, outputs[split]) == line_length;
        size_t k = 0;
        while (k < counts.size() && (counts[k].split != split || counts[k].source != source)) ++k;
        if (k == counts.size()) { Count c = {split, source, 0, 0}; counts.push_back(c); }
        ++counts[k].documents;
        counts[k].bytes += text_bytes;
    }
    for (int i = 0; i < 3; ++i) if (std::fclose(outputs[i])) ok = false;
    if (!ok) { fail(error, error_size, "Split output write failed"); return 1; }
    std::string json = "[";
    for (size_t k = 0; k < counts.size(); ++k) {
        if (k) json += ", ";
        json += "[" + std::to_string(unsigned(counts[k].split)) + ", ";
        escape(counts[k].source, json);
        json += ", " + std::to_string(counts[k].documents) + ", " + std::to_string(counts[k].bytes) + "]";
    }
    json += "]";
    *summary = static_cast<char*>(std::malloc(json.size() + 1));
    if (!*summary) { fail(error, error_size, "Out of memory"); return 1; }
    std::memcpy(*summary, json.c_str(), json.size() + 1);
    return 0;
}

void bltc_free(char* pointer) { std::free(pointer); }

}  // extern "C"
