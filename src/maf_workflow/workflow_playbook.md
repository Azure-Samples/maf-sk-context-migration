# Schedule Allocation Playbook

This playbook captures the rules we use during demonstrations of the workforce
allocation workflow. Agents can reference it to reinforce decisions discussed
throughout the orchestration pipeline.

## Objectives

- Guarantee coverage for every open shift in the staffing schedule.
- Highlight conflicts introduced by last-minute updates in Cosmos DB records.
- Escalate structural gaps, such as shifts without certified personnel.

## Allocation Checklist

1. Validate that each shift lists at least one on-site technician and one
   supervisor.
2. When a schedule row contains an `isCritical` flag, confirm that a backup
   resource is named in the updates feed.
3. If HTTP insights suggest severe weather or transportation incidents,
   reassign any impacted field teams to remote activities.
4. Summarise the impact area, recommended action, and owners for every
   discrepancy before closing the workflow.
