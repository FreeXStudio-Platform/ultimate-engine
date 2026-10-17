---
id: WF-201
classification: public
title: How This Engine Analyzes a Contract
surface: web
audience: technical
owner: doc-system
status: draft
export_allowed: true
last_reviewed: 2026-07-05
---

# How This Engine Analyzes a Contract

This engine runs a defensive, multi-stage pipeline over submitted smart contract source. This
document explains the shape of that pipeline at a high level — what happens, not how the
detection engine decides what counts as a finding (that is proprietary and never published;
see `CLASSIFICATION.md`).

## Overview

A submission moves through intake, parsing, and the static-analysis engine before a report is
produced. Every stage is deterministic and auditable from the outside; internals of the
detection engine itself are not disclosed.

<!-- figure:sample-flow -->

## Supported Chains

The table below lists the chains this engine currently supports for static analysis.

| Chain | Language | Status |
|---|---|---|
| Ethereum | Solidity | GA |
| Starknet | Cairo | GA |
| Solana | Rust (Anchor) | Beta |
