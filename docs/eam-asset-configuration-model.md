# EAM Startup Asset Configuration Model

This document defines support for the EAM startup workbook structure (provided by the EAM vendor).

## 1. Source Sheets (from workbook)

- Business Unit
- Cost Center
- Section
- Asset Types
- Asset Statuses
- Asset Groups
- Assets

## 2. Canonical Naming Standard (English-only)

- `Isletme` -> `business_unit`
- `Sarfyeri` -> `cost_center`
- `Kisim` -> `section`
- `Varlik` -> `asset`
- `Varlik Turu` -> `asset_type`
- `Varlik Durumu` -> `asset_status`
- `Varlik Grubu` -> `asset_group`

## 3. Required Data Model

### 3.1 Master Tables

- `business_unit` (`code`, `name`)
- `cost_center` (`code`, `name`, `business_unit_code`)
- `section` (`code`, `name`, `cost_center_code`)
- `asset_type` (`code`, `name`)
- `asset_status` (`code`, `name`)
- `asset_group` (`code`, `name`)

### 3.2 Asset Table

`asset` fields:

- `asset_code` (unique)
- `asset_name`
- `parent_asset_code` (nullable, self reference)
- `asset_type_code`
- `asset_status_code`
- `asset_group_code`
- `section_code`
- `cost_center_code`
- `business_unit_code`
- `brand`
- `model`
- `serial_number`
- `is_mobile_equipment`
- `default_work_type`

## 4. Asset Dependency and Tree Rules

- `parent_asset_code` defines primary hierarchy.
- Additional dependency edges are supported via `asset_dependency` table:
  - `source_asset_code`
  - `target_asset_code`
  - `dependency_type`
  - `strength`
- Cyclic dependency detection is required.
- Multi-level traversal must be supported for impact analysis.

## 5. Import Order

1. `business_unit`
2. `cost_center`
3. `section`
4. `asset_type`, `asset_status`, `asset_group`
5. `asset`
6. `asset_dependency` (if supplied separately)

## 6. Validation and Quarantine

- Empty rows are ignored.
- Codes are trimmed and normalized.
- Duplicate keys are rejected.
- Missing lookup references move records to quarantine.
- Parent asset not found moves the row to quarantine.
- Quarantine records are reviewable and reprocessable.

## 7. Risk Binding Constraint

- Every risk must reference at least one asset.
- Risk APIs must reject requests without asset references.
- All score, treatment, and review events are asset-scoped.

