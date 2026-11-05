"""Read-only report of FineWeb documents that share an id but differ in text, from a failed native combine."""
import argparse
import gzip
import json
from pathlib import Path
import unicodedata

import numpy as np

RECORD = 128


def conflicts(output, shards):
    exact, identity, location = [], [], []
    for number, shard in enumerate(shards):
        records = np.load(output / 'work' / f'records-{number:03d}.npy', mmap_mode='r')
        if len(records) != shard['documents']:
            raise ValueError(f'Record count differs from report for shard {number}')
        exact.append(np.ascontiguousarray(records[:, :32]))
        identity.append(np.ascontiguousarray(records[:, 32:64]))
        location.append(np.stack([np.full(len(records), number, np.int64), np.arange(len(records), dtype=np.int64)], 1))
    exact, identity, location = np.concatenate(exact), np.concatenate(identity), np.concatenate(location)
    keys = identity.view(np.dtype((np.void, 32))).ravel()
    order = np.argsort(keys, kind='stable')
    same = keys[order][1:] == keys[order][:-1]
    groups, run = [], []
    for index in np.flatnonzero(same):
        if run and run[-1] != index:
            groups.append(run)
            run = []
        run = run or [index]
        run.append(index + 1)
    if run:
        groups.append(run)
    result = []
    for run in groups:
        members = order[run]
        if len({exact[member].tobytes() for member in members}) > 1:
            result.append([tuple(int(value) for value in location[member]) for member in members])
    return result


def read_lines(path, wanted):
    found = {}
    with gzip.open(path, 'rb') as stream:
        for position, line in enumerate(stream):
            if position in wanted:
                found[position] = json.loads(line)
                if len(found) == len(wanted):
                    break
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fineweb-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='failed entropy_combine output with work/records-*.npy')
    parser.add_argument('--examples', type=int, default=5)
    args = parser.parse_args()
    report = json.loads(args.fineweb_report.read_text())
    groups = conflicts(args.output, report['shards'])
    summary = {'conflicting_ids': len(groups), 'documents': sum(len(group) for group in groups),
               'largest_group': max((len(group) for group in groups), default=0),
               'shards': sorted({shard for group in groups for shard, _ in group}), 'examples': []}
    examples = groups[:args.examples]
    wanted = {}
    for group in examples:
        for shard, position in group:
            wanted.setdefault(shard, set()).add(position)
    texts = {}
    for shard, positions in wanted.items():
        path = args.fineweb_report.parent / report['shards'][shard]['path']
        for position, row in read_lines(path, positions).items():
            texts[shard, position] = row
    for group in examples:
        rows = [texts[location] for location in group]
        normalized = [' '.join(unicodedata.normalize('NFC', row['text']).split()) for row in rows]
        summary['examples'].append({
            'id': rows[0]['id'],
            'documents': [{'shard': report['shards'][shard]['path'], 'line': position,
                           'utf8_bytes': len(row['text'].encode('utf-8')), 'prefix': row['text'][:60]}
                          for (shard, position), row in zip(group, rows)],
            'normalized_equal': len(set(normalized)) == 1})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
