"""
Run context experiments across the four strategies and produce a CSV with metrics.
This is a small harness: in a real run you'd tokenize and call models; here we measure preservation of the allergy fact.
"""
import csv
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from context_eval.strategies import sliding_window, observation_masking, recursive_summarization, zone_pruning
from context_eval.generate_long_transcripts import generate_40_turn_with_allergy

STRATEGIES = {
    'sliding_window': sliding_window,
    'observation_masking': observation_masking,
    'recursive_summarization': recursive_summarization,
    'zone_pruning': zone_pruning,
}


def allergy_survives(context):
    text = ' '.join([c.get('text','') for c in context]).lower()
    return 'penicillin' in text or 'allergy' in text


def run_experiments(output_csv: str = 'context_results.csv'):
    rows = []
    for name, fn in STRATEGIES.items():
        times = []
        successes = 0
        for i in range(10):
            transcript = generate_40_turn_with_allergy(patient_id=f'p{i}')
            start = time.time()
            if name == 'sliding_window':
                ctx = fn(transcript, last_k=10)
            elif name == 'observation_masking':
                ctx = fn(transcript, keep_last_tool_outputs=3, keep_last_turns=3)
            elif name == 'recursive_summarization':
                ctx = fn(transcript, chunk_size=8)
            else:
                ctx = fn(transcript)
            end = time.time()
            times.append(end-start)
            if allergy_survives(ctx):
                successes += 1
        rows.append({'strategy': name, 'accuracy': f"{successes}/10", 'avg_latency_s': sum(times)/len(times)})
    # write CSV
    with open(output_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['strategy','accuracy','avg_latency_s'])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print('Wrote', output_csv)

if __name__ == '__main__':
    run_experiments()
