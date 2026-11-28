#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <atomic>
#include <thread>
#include <vector>

namespace {

inline uint32_t rotate(uint32_t value, int bits) { return (value << bits) | (value >> (32 - bits)); }

void sha1_block(const uint8_t* block, uint32_t* state) {
    uint32_t words[80];
    for (int index = 0; index < 16; ++index) {
        words[index] = (uint32_t{block[4 * index]} << 24) | (uint32_t{block[4 * index + 1]} << 16) |
                       (uint32_t{block[4 * index + 2]} << 8) | uint32_t{block[4 * index + 3]};
    }
    for (int index = 16; index < 80; ++index) {
        words[index] = rotate(words[index - 3] ^ words[index - 8] ^ words[index - 14] ^ words[index - 16], 1);
    }
    uint32_t a = state[0], b = state[1], c = state[2], d = state[3], e = state[4];
    for (int index = 0; index < 80; ++index) {
        uint32_t mixed, constant;
        if (index < 20) {
            mixed = (b & c) | (~b & d);
            constant = 0x5a827999U;
        } else if (index < 40) {
            mixed = b ^ c ^ d;
            constant = 0x6ed9eba1U;
        } else if (index < 60) {
            mixed = (b & c) | (b & d) | (c & d);
            constant = 0x8f1bbcdcU;
        } else {
            mixed = b ^ c ^ d;
            constant = 0xca62c1d6U;
        }
        uint32_t next = rotate(a, 5) + mixed + e + constant + words[index];
        e = d;
        d = c;
        c = rotate(b, 30);
        b = a;
        a = next;
    }
    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
    state[4] += e;
}

// Equals datasketch sha1_hash32: little-endian first four SHA1 digest bytes.
uint32_t sha1_hash32(const uint8_t* data, size_t length) {
    uint32_t state[5] = {0x67452301U, 0xefcdab89U, 0x98badcfeU, 0x10325476U, 0xc3d2e1f0U};
    size_t full = length / 64;
    for (size_t block = 0; block < full; ++block) sha1_block(data + 64 * block, state);
    uint8_t tail[128] = {};
    size_t remainder = length % 64;
    memcpy(tail, data + 64 * full, remainder);
    tail[remainder] = 0x80;
    size_t tail_length = remainder < 56 ? 64 : 128;
    uint64_t bits = static_cast<uint64_t>(length) * 8;
    for (int index = 0; index < 8; ++index) tail[tail_length - 1 - index] = static_cast<uint8_t>(bits >> (8 * index));
    sha1_block(tail, state);
    if (tail_length == 128) sha1_block(tail + 64, state);
    return __builtin_bswap32(state[0]);
}

void update(uint32_t hash, const uint64_t* multipliers, const uint64_t* offsets, int affine32, uint32_t* output) {
    constexpr uint64_t prime = (uint64_t{1} << 61) - 1;
    constexpr uint64_t maximum = (uint64_t{1} << 32) - 1;
    if (affine32) {
        uint32_t mixed = hash;
        mixed ^= mixed >> 16;
        mixed *= 0x85ebca6bU;
        mixed ^= mixed >> 13;
        mixed *= 0xc2b2ae35U;
        mixed ^= mixed >> 16;
        for (size_t permutation = 0; permutation < 128; ++permutation) {
            const uint32_t permuted = multipliers[permutation] * mixed + offsets[permutation];
            output[permutation] = permuted < output[permutation] ? permuted : output[permutation];
        }
    } else {
        for (size_t permutation = 0; permutation < 128; ++permutation) {
            const uint64_t mixed = multipliers[permutation] * hash + offsets[permutation];
            const uint32_t permuted = static_cast<uint32_t>((mixed % prime) & maximum);
            output[permutation] = permuted < output[permutation] ? permuted : output[permutation];
        }
    }
}

// Five-word shingles of text normalized by " ".join(text.casefold().split()).
void signature(const uint8_t* text, size_t length, const uint64_t* multipliers, const uint64_t* offsets,
               int affine32, std::vector<size_t>& starts, std::vector<size_t>& ends, uint32_t* output) {
    for (size_t permutation = 0; permutation < 128; ++permutation) output[permutation] = 0xffffffffU;
    starts.clear();
    ends.clear();
    for (size_t position = 0; position < length;) {
        size_t end = position;
        while (end < length && text[end] != ' ') ++end;
        starts.push_back(position);
        ends.push_back(end);
        position = end + 1;
    }
    size_t words = starts.size();
    if (words == 0) {
        update(sha1_hash32(text, 0), multipliers, offsets, affine32, output);
        return;
    }
    size_t shingles = words > 5 ? words - 4 : 1;
    for (size_t shingle = 0; shingle < shingles; ++shingle) {
        size_t last = (shingle + 5 < words ? shingle + 5 : words) - 1;
        update(sha1_hash32(text + starts[shingle], ends[last] - starts[shingle]), multipliers, offsets, affine32, output);
    }
}

}  // namespace

extern "C" void blt_minhash128(const uint32_t* hashes, size_t count,
                               const uint64_t* multipliers,
                               const uint64_t* offsets,
                               uint64_t* output, int affine32) {
    constexpr uint64_t prime = (uint64_t{1} << 61) - 1;
    constexpr uint64_t maximum = (uint64_t{1} << 32) - 1;
    for (size_t permutation = 0; permutation < 128; ++permutation) {
        output[permutation] = maximum;
    }
    for (size_t position = 0; position < count; ++position) {
        if (affine32) {
            uint32_t mixed = hashes[position];
            mixed ^= mixed >> 16;
            mixed *= 0x85ebca6bU;
            mixed ^= mixed >> 13;
            mixed *= 0xc2b2ae35U;
            mixed ^= mixed >> 16;
            for (size_t permutation = 0; permutation < 128; ++permutation) {
                const uint32_t permuted = multipliers[permutation] * mixed + offsets[permutation];
                output[permutation] = permuted < output[permutation] ? permuted : output[permutation];
            }
        } else {
            for (size_t permutation = 0; permutation < 128; ++permutation) {
                const uint64_t mixed = multipliers[permutation] * hashes[position]
                                            + offsets[permutation];
                const uint64_t permuted = (mixed % prime) & maximum;
                output[permutation] = permuted < output[permutation] ? permuted : output[permutation];
            }
        }
    }
}

extern "C" int blt_minhash128_batch(const uint8_t* data, const uint64_t* boundaries, uint64_t count,
                                    const uint64_t* multipliers, const uint64_t* offsets, int affine32,
                                    int threads, uint32_t* output) {
    if (threads < 1) return -1;
    try {
        std::atomic<uint64_t> next{0};
        auto work = [&]() {
            std::vector<size_t> starts, ends;
            for (uint64_t document = next++; document < count; document = next++) {
                signature(data + boundaries[document], boundaries[document + 1] - boundaries[document],
                          multipliers, offsets, affine32, starts, ends, output + 128 * document);
            }
        };
        std::vector<std::thread> workers;
        for (int index = 1; index < threads; ++index) workers.emplace_back(work);
        work();
        for (auto& worker : workers) worker.join();
        return 0;
    } catch (...) {
        return -2;
    }
}