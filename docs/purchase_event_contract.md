# Purchase Event Contract

**Status: Provisional — pending real anonymized data**

Candidate only, not a contract:

```text
status in ('Open', 'Paid')
and status != 'Void'
event_time = order_date
```

D0 must cross-tab status with order, fulfillment/delivery, and payment dates and sample real records. Open, Paid, and Void semantics and the purchase-intent timestamp are not frozen.
