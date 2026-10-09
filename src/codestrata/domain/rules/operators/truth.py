"""Kleene three-valued truth tables for selection and composition operators."""

from __future__ import annotations

from codestrata.domain.rules.operators.models import Truth

AND_TABLE: dict[tuple[Truth, Truth], Truth] = {
    (Truth.TRUE, Truth.TRUE): Truth.TRUE,
    (Truth.TRUE, Truth.FALSE): Truth.FALSE,
    (Truth.TRUE, Truth.UNKNOWN): Truth.UNKNOWN,
    (Truth.FALSE, Truth.TRUE): Truth.FALSE,
    (Truth.FALSE, Truth.FALSE): Truth.FALSE,
    (Truth.FALSE, Truth.UNKNOWN): Truth.FALSE,
    (Truth.UNKNOWN, Truth.TRUE): Truth.UNKNOWN,
    (Truth.UNKNOWN, Truth.FALSE): Truth.FALSE,
    (Truth.UNKNOWN, Truth.UNKNOWN): Truth.UNKNOWN,
}

OR_TABLE: dict[tuple[Truth, Truth], Truth] = {
    (Truth.TRUE, Truth.TRUE): Truth.TRUE,
    (Truth.TRUE, Truth.FALSE): Truth.TRUE,
    (Truth.TRUE, Truth.UNKNOWN): Truth.TRUE,
    (Truth.FALSE, Truth.TRUE): Truth.TRUE,
    (Truth.FALSE, Truth.FALSE): Truth.FALSE,
    (Truth.FALSE, Truth.UNKNOWN): Truth.UNKNOWN,
    (Truth.UNKNOWN, Truth.TRUE): Truth.TRUE,
    (Truth.UNKNOWN, Truth.FALSE): Truth.UNKNOWN,
    (Truth.UNKNOWN, Truth.UNKNOWN): Truth.UNKNOWN,
}

NOT_TABLE: dict[Truth, Truth] = {
    Truth.TRUE: Truth.FALSE,
    Truth.FALSE: Truth.TRUE,
    Truth.UNKNOWN: Truth.UNKNOWN,
}


def kleene_and(left: Truth, right: Truth) -> Truth:
    return AND_TABLE[(left, right)]


def kleene_or(left: Truth, right: Truth) -> Truth:
    return OR_TABLE[(left, right)]


def kleene_not(value: Truth) -> Truth:
    return NOT_TABLE[value]


def fold_and(values: tuple[Truth, ...]) -> Truth:
    acc = Truth.TRUE
    for item in values:
        acc = kleene_and(acc, item)
        if acc is Truth.FALSE:
            return Truth.FALSE
    return acc


def fold_or(values: tuple[Truth, ...]) -> Truth:
    acc = Truth.FALSE
    for item in values:
        acc = kleene_or(acc, item)
        if acc is Truth.TRUE:
            return Truth.TRUE
    return acc
