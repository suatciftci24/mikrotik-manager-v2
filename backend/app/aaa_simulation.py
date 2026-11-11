"""Run built-in memory fixtures only; no input files, environment config or service calls."""
import json
from app.simulation.aaa_transition import scenario_matrix, simulate_transition


def main():
    rows = []
    for name, request, receipt, expected, blocker in scenario_matrix():
        result, _ = simulate_transition(request, receipt)
        accepted = result.outcome == expected and (blocker is None or blocker in result.blockers)
        rows.append(dict(scenario=name, outcome=result.outcome, accepted=accepted,
                         blockers=result.blockers, replayed=result.replayed,
                         expected_audit_events=len(result.expected_audit)))
    accepted = all(row['accepted'] for row in rows)
    print(json.dumps(dict(acceptance='PASS' if accepted else 'BLOCKED',
                          label='Sentetik simülasyon başarılı' if accepted else 'Sentetik simülasyon bloke',
                          mode='AAA_IN_MEMORY_SIMULATION', live_ready=False, external_writes=False,
                          scenarios=rows), ensure_ascii=False, indent=2))
    return 0 if accepted else 1


if __name__ == '__main__':
    raise SystemExit(main())
