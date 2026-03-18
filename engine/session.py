"""Session state — tracks findings, model, and bridge for each session."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentFinding:
    """Cached finding from an agent."""
    agent_id: str
    faction: str
    task: str
    finding: str
    confidence: float
    key_points: list[str]
    sources: list[str]


@dataclass
class PeerEvalRecord:
    """Stored peer evaluation."""
    evaluator: str
    target: str
    stance: str  # agree / disagree / supplement
    reasoning: str
    strengths: list[str]
    weaknesses: list[str]
    confidence_suggestion: float


@dataclass
class RevisedFindingRecord:
    """Stored revised finding after discussion."""
    agent_id: str
    action: str  # maintain / revise / concede
    original_finding: str
    revised_finding: str
    original_confidence: float
    revised_confidence: float
    response_to_critics: str
    key_points: list[str]


@dataclass
class SessionState:
    """Tracks state for a single think session."""
    session_id: str
    question: str
    model: Any = None  # ModelProvider
    findings: dict[str, AgentFinding] = field(default_factory=dict)
    dismissed: set[str] = field(default_factory=set)
    # Evolution: peer evaluations and revised findings
    peer_evals: dict[str, list[PeerEvalRecord]] = field(default_factory=dict)  # target_id → evals received
    revised_findings: dict[str, RevisedFindingRecord] = field(default_factory=dict)  # agent_id → revised

    def add_finding(self, agent_id: str, faction: str, task: str,
                    finding: str, confidence: float,
                    key_points: list[str], sources: list[str]) -> None:
        self.findings[agent_id] = AgentFinding(
            agent_id=agent_id, faction=faction, task=task,
            finding=finding, confidence=confidence,
            key_points=key_points, sources=sources,
        )

    def add_peer_eval(self, evaluator: str, target: str, stance: str,
                      reasoning: str, strengths: list[str], weaknesses: list[str],
                      confidence_suggestion: float) -> None:
        if target not in self.peer_evals:
            self.peer_evals[target] = []
        self.peer_evals[target].append(PeerEvalRecord(
            evaluator=evaluator, target=target, stance=stance,
            reasoning=reasoning, strengths=strengths, weaknesses=weaknesses,
            confidence_suggestion=confidence_suggestion,
        ))

    def add_revised_finding(self, agent_id: str, action: str,
                            original_finding: str, revised_finding: str,
                            original_confidence: float, revised_confidence: float,
                            response_to_critics: str, key_points: list[str]) -> None:
        self.revised_findings[agent_id] = RevisedFindingRecord(
            agent_id=agent_id, action=action,
            original_finding=original_finding, revised_finding=revised_finding,
            original_confidence=original_confidence, revised_confidence=revised_confidence,
            response_to_critics=response_to_critics, key_points=key_points,
        )

    def dismiss(self, agent_id: str) -> None:
        self.dismissed.add(agent_id)

    def active_findings(self) -> list[AgentFinding]:
        return [f for f in self.findings.values() if f.agent_id not in self.dismissed]
