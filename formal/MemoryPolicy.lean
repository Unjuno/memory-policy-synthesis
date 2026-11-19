/- Abstract, total memory-reclaim policy semantics.
   THIS IS NOT A PROOF OF LINUX KERNEL SAFETY OR C CODE CORRECTNESS. -/
namespace MemoryPolicy

inductive Feature where
  | idleSec | anonKiB | psiPct
  deriving Repr, DecidableEq

structure Snapshot where
  idleSec : Nat
  anonKiB : Nat
  psiPct : Nat
  deriving Repr

inductive Expr where
  | lit : Nat → Expr
  | field : Feature → Expr
  | plus : Expr → Expr → Expr
  | minus : Expr → Expr → Expr
  | minimum : Expr → Expr → Expr
  | maximum : Expr → Expr → Expr
  | percent : Nat → Expr → Expr
  | ifGe : Feature → Nat → Expr → Expr → Expr
  deriving Repr

def feature (s : Snapshot) : Feature → Nat
  | .idleSec => min s.idleSec 86400
  | .anonKiB => min s.anonKiB 268435456
  | .psiPct => min s.psiPct 100

-- Addition is capped to match the 64-bit C implementation.
def satAdd (a b : Nat) : Nat := min (2^64 - 1) (a + b)

def evalExpr (s : Snapshot) : Expr → Nat
  | .lit n => n
  | .field f => feature s f
  | .plus x y => satAdd (evalExpr s x) (evalExpr s y)
  | .minus x y => evalExpr s x - evalExpr s y
  | .minimum x y => min (evalExpr s x) (evalExpr s y)
  | .maximum x y => max (evalExpr s x) (evalExpr s y)
  | .percent p x => (evalExpr s x * min p 100) / 100
  | .ifGe f n yes no =>
      if feature s f >= n then evalExpr s yes else evalExpr s no

def decide (e : Expr) (s : Snapshot) (maxCallKiB : Nat) : Nat :=
  if s.idleSec = 0 then 0
  else min (min maxCallKiB (feature s .anonKiB)) (evalExpr s e)

theorem decide_le_cap (e : Expr) (s : Snapshot) (cap : Nat) :
    decide e s cap ≤ cap := by
  unfold decide
  split
  · exact Nat.zero_le cap
  · exact Nat.le_trans (Nat.min_le_left _ _) (Nat.min_le_left _ _)

theorem decide_le_anon (e : Expr) (s : Snapshot) (cap : Nat) :
    decide e s cap ≤ s.anonKiB := by
  unfold decide
  split
  · exact Nat.zero_le s.anonKiB
  · exact Nat.le_trans
      (Nat.le_trans (Nat.min_le_left _ _) (Nat.min_le_right _ _))
      (Nat.min_le_left _ _)

theorem decide_zero_when_active (e : Expr) (s : Snapshot) (cap : Nat)
    (h : s.idleSec = 0) : decide e s cap = 0 := by
  simp [decide, h]
end MemoryPolicy
