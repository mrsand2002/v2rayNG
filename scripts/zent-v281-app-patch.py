#!/usr/bin/env python3
"""Zent Plus 2.8.1: persist session uptime, expose usage sync, simplify menu.

Apply ONLY after the tested v2.8 announcement/usage patch. This changes no
VPN engine code, VLESS profile handling, device binding or TLS/SNI settings.
"""
from pathlib import Path

main = Path("V2rayNG/app/src/main/java/com/v2ray/ang/ui/main")
ui_file = main / "ZentManagedScreen.kt"
src = ui_file.read_text(encoding="utf-8")

def replace_one(old, new, reason):
    global src
    n=src.count(old)
    if n!=1:
        raise SystemExit(f"Zent 2.8.1: expected exactly one {reason} anchor, got {n}")
    src=src.replace(old,new,1)

# The announcement system still presents one-time popups. The customer inbox
# menu was explicitly removed by the app owner; admin controls stay intact.
replace_one('listOf("My Profile", "Data Usage", "Announcements", "Settings", "About Zent Plus")',
            'listOf("My Profile", "Data Usage", "Settings", "About Zent Plus")',
            "customer announcement navigation")
replace_one('''                        "Announcements" -> {
                            PageHeader("Announcements") { page = "Home" }
                            ZentAnnouncementsPage(context, token)
                        }
''','',"customer announcement inbox")

replace_one('''                            Text("Device-estimated usage recorded since v2.7. " +
                                "Not exact server traffic. Resets only change the displayed totals.",
                                color = Dim, fontSize = 12.sp)''',
            '''                            Text("Usage sync: " + when {
                                usageSyncError != null -> usageSyncError!!
                                usageLastSyncMs > 0L -> "Synced — " +
                                    DateFormat.getTimeInstance(DateFormat.SHORT)
                                        .format(Date(usageLastSyncMs))
                                else -> "Waiting for the first successful update"
                            }, color = if (usageSyncError != null) Color(0xFFFFBA9E) else Dim,
                                fontSize = 12.sp)''',
            "obsolete device estimate text")

replace_one('''    var statsAvailable by remember { mutableStateOf(true) }''',
'''    var statsAvailable by remember { mutableStateOf(true) }
    var hasSeenRunning by remember { mutableStateOf(false) }
    var usageSyncError by remember { mutableStateOf<String?>(null) }
    var usageLastSyncMs by remember { mutableLongStateOf(0L) }''',
"persistent state holders")

replace_one('''            val startedAt = SystemClock.elapsedRealtime()
            var previousAt = startedAt
            var previousRx = TrafficStats.getUidRxBytes(context.applicationInfo.uid)
            var previousTx = TrafficStats.getUidTxBytes(context.applicationInfo.uid)
            statsAvailable = previousRx >= 0 && previousTx >= 0
            sessionRx = 0
            sessionTx = 0''',
'''            hasSeenRunning = true
            val tickerStartedAt = SystemClock.elapsedRealtime()
            var previousAt = tickerStartedAt
            var previousRx = TrafficStats.getUidRxBytes(context.applicationInfo.uid)
            var previousTx = TrafficStats.getUidTxBytes(context.applicationInfo.uid)
            val origin = ZentSessionClock.resume(context, previousRx, previousTx)
            val startedAt = origin.startedElapsedMs
            uptimeMs = (tickerStartedAt - startedAt).coerceAtLeast(0L)
            statsAvailable = previousRx >= 0 && previousTx >= 0
            sessionRx = if (statsAvailable && origin.rxAtStart >= 0L)
                (previousRx - origin.rxAtStart).coerceAtLeast(0L) else 0L
            sessionTx = if (statsAvailable && origin.txAtStart >= 0L)
                (previousTx - origin.txAtStart).coerceAtLeast(0L) else 0L''',
"session start should survive Activity recreation")

replace_one('''                sessionRx += rx
                sessionTx += tx''',
'''                sessionRx = if (origin.rxAtStart >= 0L)
                    (newRx - origin.rxAtStart).coerceAtLeast(0L) else 0L
                sessionTx = if (origin.txAtStart >= 0L)
                    (newTx - origin.txAtStart).coerceAtLeast(0L) else 0L''',
"session UI counters from persistent start")

replace_one('''        } else {
            rxSpeed = 0
            txSpeed = 0
            uptimeMs = 0
        }
    }
    LaunchedEffect(connecting)''',
'''        } else {
            if (hasSeenRunning) ZentSessionClock.reset(context)
            hasSeenRunning = false
            rxSpeed = 0
            txSpeed = 0
            uptimeMs = 0
        }
    }
    LaunchedEffect(connecting)''',
"clear elapsed session on observed disconnection")

# User-triggered connect/disconnect must start fresh even if the service's
# transient state update isn't observed before the Activity is recreated.
replace_one("onStartVpn()", "ZentSessionClock.reset(context); onStartVpn()",
            "user-initiated VPN connect")
replace_one('''isRunning -> { onStopVpn(); notify("VPN disconnected") }''',
            '''isRunning -> { ZentSessionClock.reset(context); onStopVpn(); notify("VPN disconnected") }''',
            "user-initiated VPN disconnect")

old_effect='''            val initial = runCatching { ZentApi.fetchUsage(context, token) }.getOrNull()
            if (initial != null) accountLifetime = initial
            while (isActive) {
                if (statsAvailable) {
                    val current = runCatching {
                        usageTracker.sample(activeUsername, isRunning)
                    }.getOrNull()
                    if (current != null) {
                        val sent = runCatching {
                            ZentApi.uploadUsage(context, token, current)
                        }.getOrNull()
                        if (sent != null) accountLifetime = sent
                    }
                }
                delay(30_000L)
            }'''
new_effect='''            val initial = runCatching { ZentApi.fetchUsage(context, token) }
            initial.onSuccess { accountLifetime = it }
                .onFailure { usageSyncError = "Server unavailable — retrying" }
            while (isActive) {
                if (statsAvailable) {
                    val sample = runCatching {
                        usageTracker.sample(activeUsername, isRunning)
                    }
                    sample.onSuccess { current ->
                        val result = runCatching { ZentApi.uploadUsage(context, token, current) }
                        result.onSuccess {
                            accountLifetime = it
                            usageSyncError = null
                            usageLastSyncMs = System.currentTimeMillis()
                        }.onFailure {
                            usageSyncError = "Upload failed — retrying"
                        }
                    }.onFailure { usageSyncError = "Device counter read failed" }
                } else {
                    usageSyncError = "Traffic counters unavailable on this phone"
                }
                delay(30_000L)
            }'''
replace_one(old_effect,new_effect,"report sync failures instead of silently ignoring")

assert 'ZentAnnouncementPopup(context, token)' in src, "Popups must remain"
assert 'ZentAnnouncementsPage(context, token)' not in src, "No customer announcements tab"
assert '"Announcements" -> {' not in src
assert 'InfoCard("All-Time Usage"' in src and 'InfoCard("This Month"' in src
assert 'ZentSessionClock.resume(context, previousRx, previousTx)' in src
assert 'ZentApi.uploadUsage(context, token, current)' in src
assert "Device-estimated usage recorded since v2.7" not in src
ui_file.write_text(src,encoding="utf-8")
clock=Path("scripts/zent-v281/ZentSessionClock.kt")
assert clock.is_file()
(main/"ZentSessionClock.kt").write_text(clock.read_text(encoding="utf-8"),encoding="utf-8")
print("Zent Plus 2.8.1: session clock, usage sync state and customer menu patch applied.")
