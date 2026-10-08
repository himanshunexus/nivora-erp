# Purchase Order Workflow

This workflow describes the Purchase Orders experience from the visible procurement screen through receiving and quality release.

```dot
digraph PurchaseOrderWorkflow {
    graph [
        rankdir=TB,
        splines=ortho,
        nodesep=0.35,
        ranksep=0.55,
        bgcolor="#F8FAFC",
        pad=0.25
    ];

    node [
        fontname="Arial",
        fontsize=12,
        color="#0F172A",
        fontcolor="#0F172A",
        penwidth=1.5,
        margin="0.16,0.10"
    ];

    edge [
        fontname="Arial",
        fontsize=10,
        color="#0F172A",
        fontcolor="#0F172A",
        penwidth=1.5,
        arrowsize=0.75
    ];

    start [
        label="Start",
        shape=oval,
        style="filled",
        fillcolor="#3B82F6",
        fontcolor="#FFFFFF"
    ];

    open [
        label="Open Purchase Orders",
        shape=box,
        style="filled",
        fillcolor="#3B82F6",
        fontcolor="#FFFFFF"
    ];

    input [
        label="Select Supplier and Items",
        shape=parallelogram,
        style="filled",
        fillcolor="#E2E8F0",
        fontcolor="#475569"
    ];

    valid [
        label="Order Data Valid?",
        shape=diamond,
        style="filled",
        fillcolor="#E2E8F0",
        fontcolor="#475569"
    ];

    correct [
        label="Correct Order Details",
        shape=box,
        style="filled",
        fillcolor="#EF4444",
        fontcolor="#FFFFFF"
    ];

    submit [
        label="Submit Purchase Order",
        shape=box,
        style="filled",
        fillcolor="#3B82F6",
        fontcolor="#FFFFFF"
    ];

    receive [
        label="Record Goods Receipt",
        shape=parallelogram,
        style="filled",
        fillcolor="#E2E8F0",
        fontcolor="#475569"
    ];

    inspect [
        label="Inspect Received Lot",
        shape=box,
        style="filled",
        fillcolor="#3B82F6",
        fontcolor="#FFFFFF"
    ];

    approved [
        label="Quality Approved?",
        shape=diamond,
        style="filled",
        fillcolor="#E2E8F0",
        fontcolor="#475569"
    ];

    release [
        label="Release Stock",
        shape=box,
        style="filled",
        fillcolor="#22C55E",
        fontcolor="#FFFFFF"
    ];

    reject [
        label="Reject or Rework Lot",
        shape=box,
        style="filled",
        fillcolor="#EF4444",
        fontcolor="#FFFFFF"
    ];

    end [
        label="End",
        shape=oval,
        style="filled",
        fillcolor="#22C55E",
        fontcolor="#FFFFFF"
    ];

    start -> open;
    open -> input;
    input -> valid;
    valid -> submit [label="Yes / Valid"];
    valid -> correct [label="No / Fix"];
    correct -> input;
    submit -> receive;
    receive -> inspect;
    inspect -> approved;
    approved -> release [label="Yes / Approved"];
    approved -> reject [label="No / Rejected"];
    release -> end;
    reject -> end;
}
```

## Node semantics

| Shape | Meaning | Workflow nodes |
|---|---|---|
| Oval | Start or end state | Start, End |
| Rectangle | Application process | Open, Correct, Submit, Inspect, Release, Reject |
| Diamond | Decision gate | Order Data Valid, Quality Approved |
| Parallelogram | User-entered or recorded data | Select Supplier and Items, Record Goods Receipt |

## Application mapping

- `Open Purchase Orders` maps to `/operations/purchase-orders/`.
- `Select Supplier and Items` maps to the purchase-order creation form.
- `Submit Purchase Order` creates a submitted purchase order and its lines.
- `Record Goods Receipt` creates a goods receipt, inventory lot, and pending QC inspection.
- `Inspect Received Lot` maps to the Quality queue and quality decision form.
- `Release Stock` marks the lot available and increases product stock.
- `Reject or Rework Lot` leaves rejected quantity unavailable; partial acceptance releases only the accepted quantity.
- Both completed branches return to the operational end state with activity and notification records.

## Visual tokens

| Token | Value | Usage |
|---|---|---|
| Canvas | `#F8FAFC` | Diagram background |
| Text and borders | `#0F172A` | Labels, outlines, connectors |
| Primary action | `#3B82F6` | Main path and active process nodes |
| Success | `#22C55E` | Approved and completed path |
| Warning or error | `#EF4444` | Correction and rejection path |
| Neutral | `#E2E8F0` with `#475569` text | Inputs and decision gates |
