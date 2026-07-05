# quantum-solar

Quantum computing approach to residential battery charge/discharge scheduling
under time-of-use electricity pricing.

Given a day split into `T` time slots — each with a solar generation, household
load, and electricity price — decide when a home battery should charge, discharge,
or idle to minimize the electricity bill, subject to battery capacity and
return-to-initial state-of-charge constraints. The schedule is formulated as a
QUBO and solved with QAOA on the Qiskit Aer simulator, validated against exact
classical baselines (brute-force enumeration on tiny instances and a polynomial
dynamic-programming solver at scale).

See [CLAUDE.md](CLAUDE.md) for architecture and development commands.
