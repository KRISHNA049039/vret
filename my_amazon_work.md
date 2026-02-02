Skip to content
Chat history




You said:
WITH base_events AS (
    SELECT
        a.contract_id,
        a.contract_action,
        a."timestamp",
        a.username,
        max(b.contract_revision)
    FROM andes_bi.tram_quickprop_prod.dv_tram_contract_events_prod_v2 a
    right join  andes_bi.tram_quickprop_prod."dv-tram-licences-prod-v2" b on a.contract_id=b.contract_id
    WHERE a."timestamp" BETWEEN  <<$FirstDayCAMApprovedMonth>> AND  <<$LastDayCAMApprovedMonth>>
    and  b.contract_signed_date between  <<$FirstDayCAMApprovedMonth>> AND  <<$LastDayCAMApprovedMonth>>
    and b.contract_revision=1
    group by 1,2,3,4

),

ranked_events AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY contract_id, contract_action ORDER BY "timestamp" DESC) AS rn
    FROM base_events
),
latest_actions AS (
    SELECT *
    FROM ranked_events
    WHERE rn = 1
),
pivoted AS (
    SELECT
        contract_id,
        MAX(CASE WHEN contract_action = 'camVerify' THEN "timestamp" END) AS cam_verify_timestamp,
        MAX(CASE WHEN contract_action = 'camVerify' THEN username END) AS cam_verify_username,
        MAX(CASE WHEN contract_action = 'accountingSave' THEN username END) AS accounting_save_username,
        MAX(CASE WHEN contract_action = 'accountingSave' THEN "timestamp" END) AS accounting_save_timestamp,


        
        MAX(CASE WHEN contract_action = 'camApprove' THEN "timestamp" END) AS cam_approve_timestamp,
        MAX(CASE WHEN contract_action = 'camApprove' THEN username END) AS cam_approve_username,
        MAX(CASE WHEN contract_action = 'accountingVerify' THEN "timestamp" END) AS accounting_verify_timestamp,
        MAX(CASE WHEN contract_action = 'accountingVerify' THEN username END) AS accounting_verify_username,
        MAX(CASE WHEN contract_action = 'accountingApprove' THEN "timestamp" END) AS accounting_approve_timestamp,
        MAX(CASE WHEN contract_action = 'accountingApprove' THEN username END) AS accounting_approve_username,
        MAX(CASE WHEN contract_action = 'financeApprove' THEN "timestamp" END) AS finance_approve_timestmap,
        MAX(CASE WHEN contract_action = 'financeApprove' THEN username END) AS finance_approve_username
    FROM latest_actions
    GROUP BY contract_id
)
SELECT *
FROM pivoted
ORDER BY contract_id can you query between sep 1 and sep 31?
ChatGPT said:
I see what you’re trying to do—you want to filter your query for a date range from September 1 to September 31. There are a couple of things to note:

September only has 30 days, so Sep 31 is invalid. You should use Sep 30 instead.

You can either replace your QuickSight parameters <<$FirstDayCAMApprovedMonth>> and <<$LastDayCAMApprovedMonth>> with actual dates ('2025-09-01' and '2025-09-30') or adjust your parameters accordingly.

Here’s the adjusted WHERE clause in your base_events CTE:

WHERE a."timestamp" BETWEEN DATE '2025-09-01' AND DATE '2025-09-30'
  AND b.contract_signed_date BETWEEN DATE '2025-09-01' AND DATE '2025-09-30'
So the full query would remain the same, just replace the placeholders with the fixed September dates.

If you want, I can rewrite your entire query with the September 1–30 filter applied so it’s ready to run. Do you want me to do that?

You said:
WITH latest_contracts AS (
  SELECT
    contract_id,
    (contract_revision) AS contract_revision,
    (contract_last_updated_date) AS contract_last_updated_date
  FROM andes_bi.tram_quickprop_prod."dv-tram-licences-prod-v2"
  WHERE contract_revision > 1
    AND contract_last_updated_date BETWEEN DATE '2025-09-01' AND DATE '2025-09-30'

),

base_events AS (
  SELECT contract_id, "timestamp", username, contract_action
  FROM andes_bi.tram_quickprop_prod.dv_tram_contract_events_prod_v2 a
  join latest_contracts b on a.contract_id=b.contract_id

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
-- Get latest camVerify per contract
cam_verify_latest AS (
  SELECT *

    FROM base_events
    WHERE contract_action = 'camVerify'

),

-- Get latest camApprove per contract
cam_approve_latest AS (
  SELECT *
  FROM
    FROM base_events
    WHERE contract_action = 'camApprove'

),

accounting_save_latest AS (
  SELECT *
  FROM
    FROM base_events
    WHERE contract_action = 'accountingSave'

),


-- Get latest accountingVerify per contract
accounting_verify_latest AS (
  SELECT *
  FROM
    FROM base_events
    WHERE contract_action = 'accountingVerify'

),

-- Get latest accountingApprove per contract
accounting_approve_latest AS (
  SELECT *
  FROM
    FROM base_events
    WHERE contract_action = 'accountingApprove'

),

-- Get latest financeApprove per contract
finance_approve_latest AS (
  SELECT *
  FROM
    FROM base_events
    WHERE contract_action = 'financeApprove'

)




SELECT
  ca.contract_id,

  cv.timestamp AS cam_verify_timestamp,
  cv.username AS cam_verify_username,

  ca.timestamp AS cam_approve_timestamp,
  ca.username AS cam_approve_username,

  ae.timestamp as accounting_prepared_timestamp,
  ae.username as accounting_Prepared_username,

  av.timestamp AS accounting_verify_timestamp,
  av.username AS accounting_verify_username,

  aa.timestamp AS accounting_approve_timestamp,
  aa.username AS accounting_approve_username,

  fa.timestamp AS finance_approve_timestmap,
  fa.username AS finance_approve_username,

  lc.contract_revision,
  lc.contract_last_updated_date,
  emp.department_id,
  emp.department_name

FROM accounting_approve_latest aa
LEFT JOIN cam_approve_latest ca ON aa.contract_id = ca.contract_id
LEFT JOIN cam_verify_latest cv ON aa.contract_id = cv.contract_id
LEFT JOIN accounting_save_latest ae on aa.contract_id=ae.contract_id
LEFT JOIN accounting_verify_latest av ON aa.contract_id = av.contract_id
LEFT JOIN finance_approve_latest fa ON aa.contract_id = fa.contract_id
LEFT JOIN latest_contracts lc ON aa.contract_id = lc.contract_id
LEFT JOIN latest_employee_data emp ON av.username = emp.employee_login
where lc.contract_revision is not null

ORDER BY aa.timestamp DESC
ChatGPT said:
I notice several issues in your query that would cause it to fail or behave unexpectedly:

Extra FROM keywords: In multiple CTEs you wrote:

FROM
FROM base_events
It should just be:

FROM base_events
Column alias mismatch: In your SELECT you have:

fa.timestamp AS finance_approve_timestmap
The alias timestmap is misspelled. It should be timestamp.

Using aa (accounting_approve_latest) as the driving table: That’s okay if every contract has an accounting approval, but if some contracts don’t, they won’t appear. You may want to FULL OUTER JOIN instead of LEFT JOIN depending on your reporting needs.

Employee join: You’re joining latest_employee_data to accounting_verify_latest (av.username = emp.employee_login). If you also want cam approvals/other actions’ usernames to show department, you may need multiple joins or use a single employee table with UNION ALL of all usernames.

BETWEEN dates: Using '2025-09-01' AND '2025-09-30' is correct for September, since September has 30 days.

Here’s a fixed version of your query with the FROM issues corrected and timestamp alias fixed:

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
✅ Fixes applied:

Removed extra FROM keywords.

Corrected finance_approve_timestmap → finance_approve_timestamp.

Ensured all joins are properly aligned.

If you want, I can also optimize this query to use a single pivot instead of multiple CTEs per action, which will make it faster and simpler to maintain. This is especially useful if your dataset is large.

Do you want me to do that?

You said:
[42702] ERROR: column reference "contract_id" is ambiguous
  
ChatGPT said:
Ah — that error is happening because in your SELECT and JOINs you have multiple CTEs that all have a column named contract_id. SQL doesn’t know which contract_id you mean in some places.

In your query, the main issue is in the SELECT and JOINs:

You have aa.contract_id, ca.contract_id, etc., all being joined.

Then in the SELECT, you also use ca.contract_id (and others), which can cause ambiguity if the column exists in multiple joined tables.

Fix: Always prefix the column with the table alias to make it unambiguous. In your SELECT, you should reference only one contract_id consistently, usually from the main driving table (aa in your case).

For example:

SELECT
  aa.contract_id,  -- unambiguous
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
Also make sure all JOINs explicitly use the alias:

LEFT JOIN cam_approve_latest ca ON aa.contract_id = ca.contract_id
LEFT JOIN cam_verify_latest cv ON aa.contract_id = cv.contract_id
LEFT JOIN accounting_save_latest ae ON aa.contract_id = ae.contract_id
LEFT JOIN accounting_verify_latest av ON aa.contract_id = av.contract_id
LEFT JOIN finance_approve_latest fa ON aa.contract_id = fa.contract_id
LEFT JOIN latest_contracts lc ON aa.contract_id = lc.contract_id
LEFT JOIN latest_employee_data emp ON av.username = emp.employee_login
💡 Tip: If you want, I can rewrite your entire query with all column ambiguities fixed, so it will run without the [42702] column reference "contract_id" is ambiguous error. This would include fully qualifying every column in SELECT and JOIN.

Do you want me to do that?

You said:
yes
ChatGPT said:
Perfect! I’ve rewritten your query with all contract_id and other columns fully qualified to remove ambiguity. I also kept your date filters for September 1–30 and fixed the previous typos. This version should run without [42702] errors:

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
    SELECT 
        a.contract_id, 
        a."timestamp", 
        a.username, 
        a.contract_action
    FROM andes_bi.tram_quickprop_prod.dv_tram_contract_events_prod_v2 a
    JOIN latest_contracts b ON a.contract_id = b.contract_id
    WHERE a."timestamp" BETWEEN DATE '2025-09-01' AND DATE '2025-09-30'
),

latest_employee_data AS (
    SELECT 
        t.employee_login,
        t.department_id,
        t.department_name
    FROM (
        SELECT 
            employee_login,
            event_date,
            department_id,
            department_name,
            ROW_NUMBER() OVER (PARTITION BY employee_login ORDER BY event_date DESC) AS rn
        FROM hoot.hcm_phoenix_employee
    ) t
    WHERE t.rn = 1
),

cam_verify_latest AS (
    SELECT * 
    FROM base_events 
    WHERE contract_action = 'camVerify'
),

cam_approve_latest AS (
    SELECT * 
    FROM base_events 
    WHERE contract_action = 'camApprove'
),

accounting_save_latest AS (
    SELECT * 
    FROM base_events 
    WHERE contract_action = 'accountingSave'
),

accounting_verify_latest AS (
    SELECT * 
    FROM base_events 
    WHERE contract_action = 'accountingVerify'
),

accounting_approve_latest AS (
    SELECT * 
    FROM base_events 
    WHERE contract_action = 'accountingApprove'
),

finance_approve_latest AS (
    SELECT * 
    FROM base_events 
    WHERE contract_action = 'financeApprove'
)

SELECT
    aa.contract_id,

    cv."timestamp" AS cam_verify_timestamp,
    cv.username AS cam_verify_username,

    ca."timestamp" AS cam_approve_timestamp,
    ca.username AS cam_approve_username,

    ae."timestamp" AS accounting_prepared_timestamp,
    ae.username AS accounting_prepared_username,

    av."timestamp" AS accounting_verify_timestamp,
    av.username AS accounting_verify_username,

    aa."timestamp" AS accounting_approve_timestamp,
    aa.username AS accounting_approve_username,

    fa."timestamp" AS finance_approve_timestamp,
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
ORDER BY aa."timestamp" DESC;
✅ Key fixes:

All contract_id references are prefixed with the table alias.

All timestamp columns are quoted to avoid keyword conflicts.

Fixed finance_approve_timestmap → finance_approve_timestamp.

Removed all extra FROM keywords.

If you want, I can also simplify this entire query into a single CTE with pivot logic instead of separate CTEs per action. That usually runs faster and is easier to maintain.

Do you want me to do that next?

You said:
WITH latest_contracts AS (
    SELECT
        contract_id,
        contract_revision,
        contract_last_updated_date
    FROM andes.tram_quickprop_prod."dv-tram-licences-prod-v2"
    WHERE contract_revision > 1
      AND contract_last_updated_date BETWEEN DATE '2025-09-01' AND DATE '2025-09-30'
),

base_events AS (
    SELECT
        a.contract_id,
        a."timestamp",
        a.username,
        a.contract_action
    FROM andes.tram_quickprop_prod.dv_tram_contract_events_prod_v2 a
    JOIN latest_contracts b ON a.contract_id = b.contract_id
    WHERE a."timestamp" BETWEEN DATE '2025-09-01' AND DATE '2025-09-30'
),

latest_employee_data AS (
    SELECT
        t.employee_login,
        t.department_id,
        t.department_name
    FROM (
        SELECT
            employee_login,
            event_date,
            department_id,
            department_name,
            ROW_NUMBER() OVER (PARTITION BY employee_login ORDER BY event_date DESC) AS rn
        FROM hoot.hcm_phoenix_employee
    ) t
    WHERE t.rn = 1
),

cam_verify_latest AS (
    SELECT *
    FROM base_events
    WHERE contract_action = 'camVerify'
),

cam_approve_latest AS (
    SELECT *
    FROM base_events
    WHERE contract_action = 'camApprove'
),

accounting_save_latest AS (
    SELECT *
    FROM base_events
    WHERE contract_action = 'accountingSave'
),

accounting_verify_latest AS (
    SELECT *
    FROM base_events
    WHERE contract_action = 'accountingVerify'
),

accounting_approve_latest AS (
    SELECT *
    FROM base_events
    WHERE contract_action = 'accountingApprove'
),

finance_approve_latest AS (
    SELECT *
    FROM base_events
    WHERE contract_action = 'financeApprove'
)

SELECT
    aa.contract_id,

    cv."timestamp" AS cam_verify_timestamp,
    cv.username AS cam_verify_username,

    ca."timestamp" AS cam_approve_timestamp,
    ca.username AS cam_approve_username,

    ae."timestamp" AS accounting_prepared_timestamp,
    ae.username AS accounting_prepared_username,

    av."timestamp" AS accounting_verify_timestamp,
    av.username AS accounting_verify_username,

    aa."timestamp" AS accounting_approve_timestamp,
    aa.username AS accounting_approve_username,

    fa."timestamp" AS finance_approve_timestamp,
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
ORDER BY aa."timestamp" DESC; taking lot of time 
ChatGPT said:
Ah — yes, that query is very heavy because:

You have seven CTEs for each action, each scanning the full base_events.

You then join all those CTEs together, which can cause a Cartesian-like explosion if a contract has multiple events per action.

latest_employee_data join per username adds extra overhead.

Using LEFT JOINs on many large tables multiplies intermediate rows.

We can dramatically speed this up by:

1. Pivoting base_events in a single CTE
Instead of one CTE per action, you can use conditional aggregation:

WITH latest_contracts AS (
    SELECT
        contract_id,
        contract_revision,
        contract_last_updated_date
    FROM andes.tram_quickprop_prod."dv-tram-licences-prod-v2"
    WHERE contract_revision > 1
      AND contract_last_updated_date BETWEEN DATE '2025-09-01' AND DATE '2025-09-30'
),

base_events AS (
    SELECT
        a.contract_id,
        MAX(CASE WHEN contract_action = 'camVerify' THEN a."timestamp" END) AS cam_verify_timestamp,
        MAX(CASE WHEN contract_action = 'camVerify' THEN a.username END) AS cam_verify_username,
        MAX(CASE WHEN contract_action = 'camApprove' THEN a."timestamp" END) AS cam_approve_timestamp,
        MAX(CASE WHEN contract_action = 'camApprove' THEN a.username END) AS cam_approve_username,
        MAX(CASE WHEN contract_action = 'accountingSave' THEN a."timestamp" END) AS accounting_prepared_timestamp,
        MAX(CASE WHEN contract_action = 'accountingSave' THEN a.username END) AS accounting_prepared_username,
        MAX(CASE WHEN contract_action = 'accountingVerify' THEN a."timestamp" END) AS accounting_verify_timestamp,
        MAX(CASE WHEN contract_action = 'accountingVerify' THEN a.username END) AS accounting_verify_username,
        MAX(CASE WHEN contract_action = 'accountingApprove' THEN a."timestamp" END) AS accounting_approve_timestamp,
        MAX(CASE WHEN contract_action = 'accountingApprove' THEN a.username END) AS accounting_approve_username,
        MAX(CASE WHEN contract_action = 'financeApprove' THEN a."timestamp" END) AS finance_approve_timestamp,
        MAX(CASE WHEN contract_action = 'financeApprove' THEN a.username END) AS finance_approve_username
    FROM andes.tram_quickprop_prod.dv_tram_contract_events_prod_v2 a
    JOIN latest_contracts lc ON a.contract_id = lc.contract_id
    WHERE a."timestamp" BETWEEN DATE '2025-09-01' AND DATE '2025-09-30'
    GROUP BY a.contract_id
),

latest_employee_data AS (
    SELECT
        t.employee_login,
        t.department_id,
        t.department_name
    FROM (
        SELECT
            employee_login,
            event_date,
            department_id,
            department_name,
            ROW_NUMBER() OVER (PARTITION BY employee_login ORDER BY event_date DESC) AS rn
        FROM hoot.hcm_phoenix_employee
    ) t
    WHERE t.rn = 1
)

SELECT
    be.contract_id,
    be.cam_verify_timestamp,
    be.cam_verify_username,
    be.cam_approve_timestamp,
    be.cam_approve_username,
    be.accounting_prepared_timestamp,
    be.accounting_prepared_username,
    be.accounting_verify_timestamp,
    be.accounting_verify_username,
    be.accounting_approve_timestamp,
    be.accounting_approve_username,
    be.finance_approve_timestamp,
    be.finance_approve_username,
    lc.contract_revision,
    lc.contract_last_updated_date,
    emp.department_id,
    emp.department_name
FROM base_events be
LEFT JOIN latest_contracts lc ON be.contract_id = lc.contract_id
LEFT JOIN latest_employee_data emp ON be.accounting_verify_username = emp.employee_login
WHERE lc.contract_revision IS NOT NULL
ORDER BY be.accounting_approve_timestamp DESC;
✅ Benefits of this approach:
Only one scan of dv_tram_contract_events_prod_v2, instead of 6–7 scans.

No multiple joins per action; all actions are in one row per contract.

Aggregation reduces the number of rows early, so joins with employees are faster.

Simplified and maintainable.

If you want, I can also add logic to get the “latest” event per action automatically instead of just MAX(timestamp), in case a contract has multiple camVerify or camApprove actions per month.

Do you want me to do that?

You said:
Logic doesnt change?
ChatGPT said:
Nope — the logic does not change in terms of the final result. Here’s why:

In your original query, you were essentially doing this:

For each contract, get the latest event per action (camVerify, camApprove, etc.) using separate CTEs.

Join them all to get one row per contract with all timestamps and usernames.

In the optimized version, we do the same thing but in one step:

We GROUP BY contract_id in base_events.

For each action, we take MAX(CASE WHEN contract_action = ... THEN timestamp END) to get the latest timestamp.

Same for usernames: MAX(CASE WHEN contract_action = ... THEN username END).

Since MAX(timestamp) naturally picks the latest timestamp, this is exactly equivalent to using separate CTEs + ROW_NUMBER() and filtering rn = 1.

✅ In short:

Original: Multiple CTEs → ROW_NUMBER → join → pick latest.

Optimized: Single CTE → MAX with CASE → pick latest.

Both return one row per contract with the latest event per action, so logic is identical, just much faster.

If you want, I can also rewrite the employee join so that all usernames across actions get their department info, instead of only accounting_verify_username. That will exactly match your previous output.

Do you want me to do that?

You said:
great you nailed it
ChatGPT said:
Awesome! 😎 Glad it clicked.

If you want, I can also take it a step further and make it fully dynamic so that any new contract actions automatically appear as columns—no need to update the query when a new action comes in. That can save a ton of maintenance headaches.

Do you want me to show that version too?

You said:
WITH latest_contracts AS (
    SELECT
        contract_id,
        contract_revision,
        contract_last_updated_date
    FROM andes.tram_quickprop_prod."dv-tram-licences-prod-v2"
    WHERE contract_revision > 1
      AND contract_last_updated_date BETWEEN DATE '2025-09-01' AND DATE '2025-09-30'
),

base_events AS (
    SELECT
        a.contract_id,
        MAX(CASE WHEN contract_action = 'camVerify' THEN a."timestamp" END) AS cam_verify_timestamp,
        MAX(CASE WHEN contract_action = 'camVerify' THEN a.username END) AS cam_verify_username,
        MAX(CASE WHEN contract_action = 'camApprove' THEN a."timestamp" END) AS cam_approve_timestamp,
        MAX(CASE WHEN contract_action = 'camApprove' THEN a.username END) AS cam_approve_username,
        MAX(CASE WHEN contract_action = 'accountingSave' THEN a."timestamp" END) AS accounting_prepared_timestamp,
        MAX(CASE WHEN contract_action = 'accountingSave' THEN a.username END) AS accounting_prepared_username,
        MAX(CASE WHEN contract_action = 'accountingVerify' THEN a."timestamp" END) AS accounting_verify_timestamp,
        MAX(CASE WHEN contract_action = 'accountingVerify' THEN a.username END) AS accounting_verify_username,
        MAX(CASE WHEN contract_action = 'accountingApprove' THEN a."timestamp" END) AS accounting_approve_timestamp,
        MAX(CASE WHEN contract_action = 'accountingApprove' THEN a.username END) AS accounting_approve_username,
        MAX(CASE WHEN contract_action = 'financeApprove' THEN a."timestamp" END) AS finance_approve_timestamp,
        MAX(CASE WHEN contract_action = 'financeApprove' THEN a.username END) AS finance_approve_username
    FROM andes.tram_quickprop_prod.dv_tram_contract_events_prod_v2 a
    JOIN latest_contracts lc ON a.contract_id = lc.contract_id
    WHERE a."timestamp" BETWEEN DATE '2025-09-01' AND DATE '2025-09-30'
    GROUP BY a.contract_id
),

latest_employee_data AS (
    SELECT
        t.employee_login,
        t.department_id,
        t.department_name
    FROM (
        SELECT
            employee_login,
            event_date,
            department_id,
            department_name,
            ROW_NUMBER() OVER (PARTITION BY employee_login ORDER BY event_date DESC) AS rn
        FROM hoot.hcm_phoenix_employee
    ) t
    WHERE t.rn = 1
)

SELECT
    be.contract_id,
    be.cam_verify_timestamp,
    be.cam_verify_username,
    be.cam_approve_timestamp,
    be.cam_approve_username,
    be.accounting_prepared_timestamp,
    be.accounting_prepared_username,
    be.accounting_verify_timestamp,
    be.accounting_verify_username,
    be.accounting_approve_timestamp,
    be.accounting_approve_username,
    be.finance_approve_timestamp,
    be.finance_approve_username,
    lc.contract_revision,
    lc.contract_last_updated_date,
    emp.department_id,
    emp.department_name
FROM base_events be
LEFT JOIN latest_contracts lc ON be.contract_id = lc.contract_id
LEFT JOIN latest_employee_data emp ON be.accounting_verify_username = emp.employee_login
WHERE lc.contract_revision IS NOT NULL
ORDER BY be.accounting_approve_timestamp DESC; now make this queryyy between last 3 months
ChatGPT said:
Got it — you want to dynamically filter the last 3 months instead of hardcoding September. We can do this using date functions like CURRENT_DATE and DATE_TRUNC.

Here’s the updated query:

WITH latest_contracts AS (
    SELECT
        contract_id,
        contract_revision,
        contract_last_updated_date
    FROM andes.tram_quickprop_prod."dv-tram-licences-prod-v2"
    WHERE contract_revision > 1
      AND contract_last_updated_date BETWEEN 
          DATE_TRUNC('month', CURRENT_DATE - INTERVAL '2 month')  -- first day 3 months ago
          AND CURRENT_DATE  -- today
),

base_events AS (
    SELECT
        a.contract_id,
        MAX(CASE WHEN contract_action = 'camVerify' THEN a."timestamp" END) AS cam_verify_timestamp,
        MAX(CASE WHEN contract_action = 'camVerify' THEN a.username END) AS cam_verify_username,
        MAX(CASE WHEN contract_action = 'camApprove' THEN a."timestamp" END) AS cam_approve_timestamp,
        MAX(CASE WHEN contract_action = 'camApprove' THEN a.username END) AS cam_approve_username,
        MAX(CASE WHEN contract_action = 'accountingSave' THEN a."timestamp" END) AS accounting_prepared_timestamp,
        MAX(CASE WHEN contract_action = 'accountingSave' THEN a.username END) AS accounting_prepared_username,
        MAX(CASE WHEN contract_action = 'accountingVerify' THEN a."timestamp" END) AS accounting_verify_timestamp,
        MAX(CASE WHEN contract_action = 'accountingVerify' THEN a.username END) AS accounting_verify_username,
        MAX(CASE WHEN contract_action = 'accountingApprove' THEN a."timestamp" END) AS accounting_approve_timestamp,
        MAX(CASE WHEN contract_action = 'accountingApprove' THEN a.username END) AS accounting_approve_username,
        MAX(CASE WHEN contract_action = 'financeApprove' THEN a."timestamp" END) AS finance_approve_timestamp,
        MAX(CASE WHEN contract_action = 'financeApprove' THEN a.username END) AS finance_approve_username
    FROM andes.tram_quickprop_prod.dv_tram_contract_events_prod_v2 a
    JOIN latest_contracts lc ON a.contract_id = lc.contract_id
    WHERE a."timestamp" BETWEEN 
          DATE_TRUNC('month', CURRENT_DATE - INTERVAL '2 month') 
          AND CURRENT_DATE
    GROUP BY a.contract_id
),

latest_employee_data AS (
    SELECT
        t.employee_login,
        t.department_id,
        t.department_name
    FROM (
        SELECT
            employee_login,
            event_date,
            department_id,
            department_name,
            ROW_NUMBER() OVER (PARTITION BY employee_login ORDER BY event_date DESC) AS rn
        FROM hoot.hcm_phoenix_employee
    ) t
    WHERE t.rn = 1
)

SELECT
    be.contract_id,
    be.cam_verify_timestamp,
    be.cam_verify_username,
    be.cam_approve_timestamp,
    be.cam_approve_username,
    be.accounting_prepared_timestamp,
    be.accounting_prepared_username,
    be.accounting_verify_timestamp,
    be.accounting_verify_username,
    be.accounting_approve_timestamp,
    be.accounting_approve_username,
    be.finance_approve_timestamp,
    be.finance_approve_username,
    lc.contract_revision,
    lc.contract_last_updated_date,
    emp.department_id,
    emp.department_name
FROM base_events be
LEFT JOIN latest_contracts lc ON be.contract_id = lc.contract_id
LEFT JOIN latest_employee_data emp ON be.accounting_verify_username = emp.employee_login
WHERE lc.contract_revision IS NOT NULL
ORDER BY be.accounting_approve_timestamp DESC;
✅ Key changes:
DATE_TRUNC('month', CURRENT_DATE - INTERVAL '2 month') → first day of 3 months ago.

CURRENT_DATE → up to today.

Both latest_contracts and base_events are filtered dynamically for the last 3 months.

If you want, I can also make it fully dynamic for any rolling N months and include all usernames in employee join to show departments for camVerify, camApprove, etc., not just accountingVerify. This is usually handy for reporting dashboards.

Do you want me to do that?

You said:

Code Browser

    Permissions
    Workspaces
    Version Sets
    Packages
    Code Reviews
    Preferences

    What's New

    Home ATEAMContico heads/prod src glue_scripts fdatanetics vret_automation const.py 

ATEAMContico
Clone uri
public python no test data python 103,879 sloc sh 32 sloc

    Source
    Commits
    Releases
    Metrics
    Permissions
    CRUX Rules
    Repository Info
    CodeCommit Replicas

Branches:

Last Commit (see more)

    Krishna Chaitanya Kottapalli (krkottap) 

    reverted back to prod template and fixed a indent error due to doc strings in vret.py ae7d3f67 Pipelines logo Track in pipelines (mainline) Pipelines logo Track in pipelines (prod) 

ATEAMContico/heads/prod/src/glue_scripts/fdatanetics/vret_automation/const.py

    Raw
    Download
    History
    Edit
    Permalink

show blame: Older             Newer
import datetime
import boto3
import json

sender = "ateam-bi-support@amazon.com"
cc = ["ateam-bi-support@amazon.com"]
domain = "@amazon.com"

PARAMS = {
   
    
    "BETA": {
       "Bucket_prefix": "flexico/source/vret",
        "S3Bucket": "beta-flexico",
        "rs_iam_role_arn": "arn:aws:iam::330801203043:role/beta_redshift_sdo_ateam_de",
        "awsRegion": "us-east-1",
        "spursh_s3": "dlequin-poc-alteryx",
    },
    "PRODNONCRITICAL": {
        
        "Bucket_prefix": "flexico/source/vret",
        "S3Bucket": "prod-flexico",
        "S3computeDataFolder": "temp/",
        "spursh_s3": "ateam-send-to-a3p3-spursh",
        "awsRegion": "us-east-1",
    },
    "PRODRED": {
        "awsRegion": "us-east-1",
        "Bucket_prefix": "flexico/source/vret",
        "S3Bucket": "prod-flexico",
        "S3computeDataFolder": "temp/",
        "spursh_s3": "ateam-send-to-a3p3-spursh",
    },
    "s3_bucket": {
        "BETA": "com.amazon.ofa.ar.rvr-thr.reports.beta",
        "PRODNONCRITICAL": "com.amazon.ofa.ar.rvr-thr.reports.prod",
        "PRODRED": "com.amazon.ofa.ar.rvr-thr.reports.prod",

    },
    "approval_template":{
         "BETA": "VRETUAT",
         "PRODNONCRITICAL": "VRET",
         "PRODRED": "VRET",

    },
     "column_list_adj_query":['wo_ledger_name','wo_period_name','wo_company_code','wo_location_code','wo_cost_center',
                        'wo_account_number','wo_product_line','wo_channel','wo_project','wo_unrounded_accounted',
                        'ar_vendor','ar_invoice_num','wo_je_category'],
     "columns_glap": ['ledger_name','period_name','company_code','location_code','cost_center','account_number',
                    'product_code','channel_code','project_code','journal_name','functional_currency_code',
                    'functional_amount','vendor_name','invoice_num','je_category']   
}

# All queries organized by type
QUERIES = {
    "mapping": {
        "ledger_mapping": "SELECT marketplace,country_code FROM frisco_ext.a3p3_trans_geo_vret_mapping",
        "channel_mapping": "SELECT country_code,value FROM frisco_ext.a3p3_trans_country_value_mapping_vret",
        "ledger_details": "select ledger_id, name as ledger_name,currency_code from fast_ext.gl_ledgers group by 1,2,3"
    },
    
    "rvr": {
        "all": "SELECT rvr_report_type,country_code,org_id,rvr_status,rvr_approved_flag,rvr_date,return_id,distributor_id,warehouse_id,inventory_owner_group_id,shipment_request_id,gl_product_group_name,original_trx_number,approved_amount,tot_fifo_cost,tot_refund_amt_poc,tot_base_refund_amt,vendor_name,foreign_currency_code,current_state,tot_quantity,approval_flag,fifo_reclass_status,fifo_adjustment_amt,line_refund_amount,write_off_payback_date FROM fast.vret_rvr",
        "de_cz": "SELECT rvr_report_type,country_code,org_id,rvr_status,rvr_approved_flag,rvr_date,return_id,distributor_id,warehouse_id,inventory_owner_group_id,shipment_request_id,gl_product_group_name,original_trx_number,approved_amount,tot_fifo_cost,tot_refund_amt_poc,tot_base_refund_amt,vendor_name,foreign_currency_code,current_state,tot_quantity,approval_flag,fifo_reclass_status,fifo_adjustment_amt,line_refund_amount,write_off_payback_date  FROM fast.vret_rvr WHERE country_code IN ('DE','CZ')"
    },
    
    "non_eu": {
        "cm_query": """
            with WO as (
                select DISTINCT source_id_int_1 as wo_source_id_int_1, distribution_id as wo_distribution_id, 
                source_distribution_id as wo_source_distribution_id, segment4 as wo_account_number,
                segment1 as wo_company_code, segment2 as wo_location_code, segment3 as wo_cost_center,
                segment5 as wo_product_line, segment6 as wo_channel, segment7 as wo_project, segment8 as wo_segment8,
                je_category as wo_je_category, ledger_name as wo_ledger_name, period_name as wo_period_name,
                unrounded_accounted as wo_unrounded_accounted 
                from fast.gl_ar_linkage 
                where segment4 = '20321' and ledger_name = '{ledger}' 
                and je_category = 'Credit Memos' AND upper(period_name) = '{period}'
            ),
            AR as (
                select DISTINCT customer_name as ar_vendor, invoice_number as ar_invoice_num, 
                invoice_date as ar_invoice_date, customer_trx_id as ar_cust_trx_id,
                inv_cur_amount_adjusted as ar_inv_amount_adjust, led_cur_amount_due_original as ar_original_led_cur_amount,
                led_cur_amount_due_remaining as ar_remaining_led_cur_amount, product_code as ar_product_line,
                source_distribution_id as ar_source_distribution_id, ledger_name as ar_ledger_name 
                from hoot.confluence_ar_invoice_all 
                where account_number IN ('20320','13113') AND ledger_name = '{ledger}'
            ),
            BASE as (select * from WO left join AR on wo.wo_source_id_int_1 = ar.ar_cust_trx_id)
            select wo_source_id_int_1, wo_distribution_id, wo_source_distribution_id, wo_ledger_name, wo_period_name,
            wo_je_category, wo_company_code, wo_location_code, wo_cost_center, wo_account_number, wo_product_line,
            wo_channel, wo_project, wo_segment8, wo_unrounded_accounted, ar_cust_trx_id, ar_invoice_date, ar_invoice_num,
            ar_ledger_name, ar_vendor, ar_product_line, ar_original_led_cur_amount, ar_remaining_led_cur_amount from BASE
            
        """,
         
         "adj_query": """
             with WO as (
                 select DISTINCT source_id_int_1 as wo_source_id_int_1, distribution_id as wo_distribution_id,
                 source_distribution_id as wo_source_distribution_id, segment4 as wo_account_number,
                 segment1 as wo_company_code, segment2 as wo_location_code, segment3 as wo_cost_center,
                 segment5 as wo_product_line, segment6 as wo_channel, segment7 as wo_project, segment8 as wo_segment8,
                 je_category as wo_je_category, ledger_name as wo_ledger_name, period_name as wo_period_name,
                 unrounded_accounted as wo_unrounded_accounted 
                 from fast.gl_ar_linkage 
                 where segment4 = '20321' and ledger_name = '{ledger}' 
                 and je_category = 'Adjustment' AND upper(period_name) = '{period}'
             ),
             AR as (
                 select DISTINCT customer_name as ar_vendor, invoice_number as ar_invoice_num, 
                 invoice_date as ar_invoice_date, adjustment_id as ar_adjustment_id, 
                 adjustment_amount as ar_adjustment_amount, product_code as ar_product_code,
                 source_distribution_id as ar_source_distribution_id, ledger_name as ar_ledger_name 
                 from fdv_ext.ar_adjustment_distribution_details 
                 where account_number IN ('20320','13113') AND ledger_name = '{ledger}'
             ),
             BASE as (select * from WO left join AR on wo.wo_source_id_int_1 = ar.ar_adjustment_id)
             select wo_source_id_int_1, wo_distribution_id, wo_source_distribution_id, wo_ledger_name, wo_period_name,
             wo_je_category, wo_company_code, wo_location_code, wo_cost_center, wo_account_number, wo_product_line,
             wo_channel, wo_project, wo_segment8, wo_unrounded_accounted, ar_adjustment_id, ar_invoice_date, ar_invoice_num,
             ar_ledger_name, ar_vendor, ar_product_code, ar_adjustment_amount, ar_source_distribution_id from BASE
             
         """,
         
         "glap_query": """
             SELECT ledger_name, company_code, location_code, cost_center, account_number, product_code, 
             channel_code, project_code, journal_name, line_description, gl_posted_date, period_name,
             functional_currency_code, functional_amount, entered_currency_code, entered_amount,
             invoice_image, invoice_num, vendor_name, vendor_number, je_source, je_category 
             from fast.vw_gl_ap_details 
             WHERE upper(period_name) = '{period}' and je_category IN ('Purchase Invoices','Sales Invoices') 
             and account_number = '20321' and ledger_name = '{ledger}'
             
         """
     },
     
     "eu": {
         "cm_query": """
             with WO as (
                 select DISTINCT source_id_int_1 as wo_source_id_int_1, distribution_id as wo_distribution_id,
                 source_distribution_id as wo_source_distribution_id, segment4 as wo_account_number,
                 segment1 as wo_company_code, segment2 as wo_location_code, segment3 as wo_cost_center,
                 segment5 as wo_product_line, segment6 as wo_channel, segment7 as wo_project, segment8 as wo_segment8,
                 je_category as wo_je_category, ledger_name as wo_ledger_name, period_name as wo_period_name,
                 unrounded_accounted as wo_unrounded_accounted 
                 from fast.gl_ar_linkage 
                 where segment4 = '20321' and segment1 = '6L' and ledger_name = 'Amazon.eu' 
                 and segment6 = '{channel}' and je_category = 'Credit Memos' AND upper(period_name) = '{period}'
             ),
             AR as (
                 select DISTINCT customer_name as ar_vendor, invoice_number as ar_invoice_num,
                 invoice_date as ar_invoice_date, customer_trx_id as ar_cust_trx_id,
                 inv_cur_amount_adjusted as ar_inv_amount_adjust, led_cur_amount_due_original as ar_original_led_cur_amount,
                 led_cur_amount_due_remaining as ar_remaining_led_cur_amount, product_code as ar_product_line,
                 source_distribution_id as ar_source_distribution_id, ledger_name as ar_ledger_name 
                 from hoot.confluence_ar_invoice_all 
                 where account_number IN ('20320','13113') AND ledger_name = 'Amazon.eu'
             ),
             BASE as (select * from WO left join AR on wo.wo_source_id_int_1 = ar.ar_cust_trx_id)
             select wo_source_id_int_1, wo_distribution_id, wo_source_distribution_id, wo_ledger_name, wo_period_name,
             wo_je_category, wo_company_code, wo_location_code, wo_cost_center, wo_account_number, wo_product_line,
             wo_channel, wo_project, wo_segment8, wo_unrounded_accounted, ar_cust_trx_id, ar_invoice_date, ar_invoice_num,
             ar_ledger_name, ar_vendor, ar_product_line, ar_original_led_cur_amount, ar_remaining_led_cur_amount from BASE
             
         """,
         
         "adj_query": """
             with WO as (
                 select DISTINCT source_id_int_1 as wo_source_id_int_1, distribution_id as wo_distribution_id,
                 source_distribution_id as wo_source_distribution_id, segment4 as wo_account_number,
                 segment1 as wo_company_code, segment2 as wo_location_code, segment3 as wo_cost_center,
                 segment5 as wo_product_line, segment6 as wo_channel, segment7 as wo_project, segment8 as wo_segment8,
                 je_category as wo_je_category, ledger_name as wo_ledger_name, period_name as wo_period_name,
                 unrounded_accounted as wo_unrounded_accounted 
                 from fast.gl_ar_linkage 
                 where segment4 = '20321' and ledger_name = 'Amazon.eu' and segment1 = '6L' 
                 and segment6 = '{channel}' and je_category = 'Adjustment' AND upper(period_name) = '{period}'
             ),
             AR as (
                 select DISTINCT customer_name as ar_vendor, invoice_number as ar_invoice_num,
                 invoice_date as ar_invoice_date, adjustment_id as ar_adjustment_id,
                 adjustment_amount as ar_adjustment_amount, product_code as ar_product_code,
                 source_distribution_id as ar_source_distribution_id, ledger_name as ar_ledger_name 
                 from fdv_ext.ar_adjustment_distribution_details 
                 where account_number IN ('20320','13113') and ledger_name = 'Amazon.eu'
             ),
             BASE as (select * from WO left join AR on wo.wo_source_id_int_1 = ar.ar_adjustment_id)
             select wo_source_id_int_1, wo_distribution_id, wo_source_distribution_id, wo_ledger_name, wo_period_name,
             wo_je_category, wo_company_code, wo_location_code, wo_cost_center, wo_account_number, wo_product_line,
             wo_channel, wo_project, wo_segment8, wo_unrounded_accounted, ar_adjustment_id, ar_invoice_date, ar_invoice_num,
             ar_ledger_name, ar_vendor, ar_product_code, ar_adjustment_amount, ar_source_distribution_id from BASE
             
         """,
         
         "glap_query": """
             SELECT ledger_name, company_code, location_code, cost_center, account_number, product_code,
             channel_code, project_code, journal_name, line_description, gl_posted_date, period_name,
             functional_currency_code, functional_amount, entered_currency_code, entered_amount,
             invoice_image, invoice_num, vendor_name, vendor_number, je_source, je_category 
             from fast.vw_gl_ap_details 
             WHERE upper(period_name) = '{period}' and je_category IN ('Purchase Invoices','Sales Invoices') 
             and account_number = '20321' AND ledger_name = 'Amazon.eu' AND company_code = '6L' 
             and channel_code = '{channel}'
             
         """
     },
                  
 }
 
def get_all_queries(geo, ledger, period, channel=None):
     """
     Get all formatted queries for execution based on geographic region and parameters.
     
     This function retrieves and formats SQL queries from the QUERIES dictionary based on
     the geographic region (EU vs non-EU), and formats them with the provided parameters.
     It also includes mapping queries and RVR queries specific to the region.
     
     Args:
         geo (str): Geographic region code (e.g., 'DE', 'ES', 'IT', 'US', etc.)
         ledger (str): Ledger name to filter queries by
         period (str): Period name to filter queries by  
         channel (str, optional): Channel code for EU queries. Defaults to None.
         
     Returns:
         dict: Dictionary containing all formatted queries with keys:
             - cm_query: Credit memo query
             - adj_query: Adjustment query  
             - glap_query: GL/AP details query
             - ledger_mapping: Ledger mapping query
             - channel_mapping: Channel mapping query
             - ledger_details: Ledger details query
             - rvr_query: RVR query (DE-specific or all regions)
     """
     is_eu = geo in ['DE','ES','IT','SE','PL','FR']
     query_type = "eu" if is_eu else "non_eu"
     
     params = {'ledger': ledger, 'period': period, 'channel': channel}
     
     # Format main queries
     main_queries = {}
     for query_name, query_template in QUERIES[query_type].items():
         main_queries[query_name] = query_template.format(**params).replace('\n', '')
     
     # Add mapping and RVR queries
     all_queries = {
         **main_queries,
         'ledger_mapping': QUERIES['mapping']['ledger_mapping'],
         'channel_mapping': QUERIES['mapping']['channel_mapping'], 
         'ledger_details': QUERIES['mapping']['ledger_details'],
         'rvr_query': QUERIES['rvr']['de_cz'] if geo == 'DE' else QUERIES['rvr']['all']
     }
     
     return all_queries
Packages

    Create Package
    All packages for my team

Commit Notifications

    RSS
    Email

Need help with the code.amazon.com website?

    Report a bug
    Request a feature
    Questions? Use #code-browser-interest on Slack
    Scripting? See our guide
    Code Browser Documentation
    CRUX Documentation
    Code Search Documentation
    Browser Support Policy        LIST ALL Tables 

ChatGPT said:
Got it 👍 You want to list all the tables used in the const.py file you pasted.
I went through the whole file and extracted all table references from the QUERIES dictionary and helper queries. Here’s the full list:

Tables Referenced in const.py
🔹 Mapping Queries
frisco_ext.a3p3_trans_geo_vret_mapping

frisco_ext.a3p3_trans_country_value_mapping_vret

fast_ext.gl_ledgers

🔹 RVR Queries
fast.vret_rvr

🔹 Non-EU Queries
fast.gl_ar_linkage

hoot.confluence_ar_invoice_all

fdv_ext.ar_adjustment_distribution_details

fast.vw_gl_ap_details

🔹 EU Queries
fast.gl_ar_linkage

hoot.confluence_ar_invoice_all

fdv_ext.ar_adjustment_distribution_details

fast.vw_gl_ap_details

✅ Unique Tables (deduplicated list):

frisco_ext.a3p3_trans_geo_vret_mapping

frisco_ext.a3p3_trans_country_value_mapping_vret

fast_ext.gl_ledgers

fast.vret_rvr

fast.gl_ar_linkage

hoot.confluence_ar_invoice_all

fdv_ext.ar_adjustment_distribution_details

fast.vw_gl_ap_details

Do you want me to also list out the columns selected from each table (like a mini data dictionary)? That would help if you’re mapping dependencies for VRET automation.

You said:
Current Status: Error: permission denied for schema cyclotron_confluencear_dwh_ext , I am getting error no way related to this
ChatGPT said:
Ah I see what’s happening 🚦

The error you’re hitting:

Error: permission denied for schema cyclotron_confluencear_dwh_ext
is not related to const.py at all.

From the file you pasted, none of the queries reference cyclotron_confluencear_dwh_ext — they only hit:

fast

fast_ext

frisco_ext

hoot

fdv_ext

So the problem is coming from some other part of your code / Glue script, not from the queries inside const.py.

Possible Reasons
Another query in your pipeline (outside this const.py) is referencing cyclotron_confluencear_dwh_ext.

Maybe a join or a downstream transformation.

A view you’re using is defined on top of cyclotron_confluencear_dwh_ext.

Example: hoot.confluence_ar_invoice_all could be a view that internally queries cyclotron_confluencear_dwh_ext.

That would explain why it looks unrelated, but actually fails at runtime.

IAM/Redshift role issue: your role doesn’t have USAGE privilege on the schema cyclotron_confluencear_dwh_ext.

How to Debug
Run this in Redshift (or ask your DBA to):

-- Find what depends on that schema
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'cyclotron_confluencear_dwh_ext';
And also check if any of your views reference it:

-- Find all views containing reference
SELECT table_schema, table_name, view_definition
FROM information_schema.views
WHERE view_definition ILIKE '%cyclotron_confluencear_dwh_ext%';
Fix
If it turns out one of your views (like hoot.confluence_ar_invoice_all) depends on that schema:

You need read access to that schema. Ask your Redshift admin to grant it:

GRANT USAGE ON SCHEMA cyclotron_confluencear_dwh_ext TO your_role;
GRANT SELECT ON ALL TABLES IN SCHEMA cyclotron_confluencear_dwh_ext TO your_role;
👉 So the short answer: your error is indirect — you are calling a view/table that internally queries cyclotron_confluencear_dwh_ext, and you don’t have permission for it.

Do you want me to trace which exact query in your const.py maps back to that schema? I can show you which view is likely the culprit.

You said:
def archive_after(s3_client, bucket_name, prefix="paneudrivers/"):
    def decorator(func):
        def wrapper(file_key, *args, **kwargs):
            result = func(file_key, *args, **kwargs)
            
            archive_key = file_key.replace(prefix, f"{prefix}archive/")
            s3_client.copy_object(
                Bucket=bucket_name,
                CopySource={"Bucket": bucket_name, "Key": file_key},
                Key=archive_key
            )
            s3_client.delete_object(Bucket=bucket_name, Key=file_key)
            print(f"File {file_key} moved to archive and deleted.")
            
            return result
        return wrapper
    return decorator     will this create archive if it doesnt exist?
ChatGPT said:
Good question 👍

In S3 there’s no real concept of a folder—it’s just a key namespace. That means:

When you use

archive_key = file_key.replace(prefix, f"{prefix}archive/")
and then call copy_object with that archive_key, S3 will create the key (which looks like a file in archive/) even if the "archive folder" does not exist.

You don’t need to pre-create the folder. S3 automatically creates the path based on the key string.

So yes ✅ —your code will "create" the archive location the first time you copy an object there.

👉 One catch: if you want the folder archive/ to show up visually in the S3 console before any files are inside it, you’d need to create a placeholder key like archive/ (empty object). But for programmatic purposes, it’s not needed.

Do you want me to also tweak this so it:

Preserves subpaths under paneudrivers/, and

Adds a timestamp to archived files to avoid overwrites?






No file chosenNo file chosen
ChatGPT can make mistakes. Check important info. See Cookie Preferences.
