WITH latest_contracts AS (
  SELECT
    contract_id,
    contract_revision,
    contract_last_updated_date
  FROM andes_bi.tram_quickprop_prod."dv-tram-licences-prod-v2"
  WHERE contract_revision > 1
    AND contract_last_updated_date BETWEEN DATE '2025-09-01' AND DATE '2025-09-30'
),

base_events AS (
  SELECT contract_id, "timestamp", username, contract_action
  FROM andes_bi.tram_quickprop_prod.dv_tram_contract_events_prod_v2 a
  JOIN latest_contracts b ON a.contract_id = b.contract_id
  WHERE "timestamp" BETWEEN DATE '2025-09-01' AND DATE '2025-09-30'
),

latest_employee_data AS (
  SELECT employee_login,
         department_id,
         department_name
  FROM (
      SELECT employee_login,
             event_date,
             department_id,
             department_name,
             ROW_NUMBER() OVER (PARTITION BY employee_login ORDER BY event_date DESC) AS rn
      FROM hoot.hcm_phoenix_employee
  ) t
  WHERE rn = 1
),

cam_verify_latest AS (
  SELECT * FROM base_events WHERE contract_action = 'camVerify'
),

cam_approve_latest AS (
  SELECT * FROM base_events WHERE contract_action = 'camApprove'
),

accounting_save_latest AS (
  SELECT * FROM base_events WHERE contract_action = 'accountingSave'
),

accounting_verify_latest AS (
  SELECT * FROM base_events WHERE contract_action = 'accountingVerify'
),

accounting_approve_latest AS (
  SELECT * FROM base_events WHERE contract_action = 'accountingApprove'
),

finance_approve_latest AS (
  SELECT * FROM base_events WHERE contract_action = 'financeApprove'
)

SELECT
  ca.contract_id,

  cv.timestamp AS cam_verify_timestamp,
  cv.username AS cam_verify_username,

  ca.timestamp AS cam_approve_timestamp,
  ca.username AS cam_approve_username,

  ae.timestamp AS accounting_prepared_timestamp,
  ae.username AS accounting_prepared_username,

  av.timestamp AS accounting_verify_timestamp,
  av.username AS accounting_verify_username,

  aa.timestamp AS accounting_approve_timestamp,
  aa.username AS accounting_approve_username,

  fa.timestamp AS finance_approve_timestamp,
  fa.username AS finance_approve_username,

  lc.contract_revision,
  lc.contract_last_updated_date,
  emp.department_id,
  emp.department_name

FROM accounting_approve_latest aa
LEFT JOIN cam_approve_latest ca ON aa.contract_id = ca.contract_id
LEFT JOIN cam_verify_latest cv ON aa.contract_id = cv.contract_id
LEFT JOIN accounting_save_latest ae ON aa.contract_id = ae.contract_id
LEFT JOIN accounting_verify_latest av ON aa.contract_id = av.contract_id
LEFT JOIN finance_approve_latest fa ON aa.contract_id = fa.contract_id
LEFT JOIN latest_contracts lc ON aa.contract_id = lc.contract_id
LEFT JOIN latest_employee_data emp ON av.username = emp.employee_login
WHERE lc.contract_revision IS NOT NULL
ORDER BY aa.timestamp DESC;
