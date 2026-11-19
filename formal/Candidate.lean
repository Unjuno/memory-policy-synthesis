import MemoryPolicy
namespace Candidate
open MemoryPolicy

def candidate : Expr := (Expr.ifGe Feature.idleSec 10 (Expr.percent 25 (Expr.field Feature.anonKiB)) (Expr.lit 0))

theorem cap_safe (s : Snapshot) (cap : Nat) :
    decide candidate s cap ≤ cap := decide_le_cap candidate s cap

theorem anon_safe (s : Snapshot) (cap : Nat) :
    decide candidate s cap ≤ s.anonKiB := decide_le_anon candidate s cap

theorem zero_when_active (s : Snapshot) (cap : Nat) (h : s.idleSec = 0) :
    decide candidate s cap = 0 := decide_zero_when_active candidate s cap h
end Candidate
