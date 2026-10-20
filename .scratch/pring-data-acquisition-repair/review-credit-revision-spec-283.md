269→282仅新增255行，旧36场景/生产未改；未跑测试。

279两项已修：6111读claims时间；6191–6201核新trace及旧trace不变，known排除旧采用ID。

P2：unknown采用集合仍不完整。6187仅验证旧父项是subset，未来修订ID混入也能通过；6237–6248无target分支仅验行/trace。按issue19:30–31，补断言未知target/PUBLIC的revision.claim_ids与实际采用不交；无target SYSTEM采用新父项且排除被替代GDP ID。

无越界：原时间戳下改值触发未知PUBLIC（official_context.py:485–510）；历史target与无target SYSTEM区别符合既有PMI/LPR例及spec:111。281真实2通过62.52秒；283仅进度点，不预判通过。
