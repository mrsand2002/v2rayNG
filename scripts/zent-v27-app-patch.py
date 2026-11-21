#!/usr/bin/env python3
"""Add one-phone login and device-estimated lifetime usage to the clean v2.6 UI.
Run AFTER apply_zent.py and the v2.6 diagnostic removal.
Keep existing VPN native/TLS/SNI logic unchanged.
"""
from pathlib import Path

main = Path("V2rayNG/app/src/main/java/com/v2ray/ang/ui/main")
api_path = main / "ZentApi.kt"
ui_path = main / "ZentManagedScreen.kt"
api = api_path.read_text(encoding="utf-8")
ui = ui_path.read_text(encoding="utf-8")

def replace_one(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Unexpected v2.6 anchor {label}: {count}")
    return text.replace(old, new, 1)

api = replace_one(api, "import kotlinx.coroutines.Dispatchers\n",
    "import android.content.Context\nimport kotlinx.coroutines.Dispatchers\n", "API Context import")
api = replace_one(api,
    "private suspend fun request(path: String, token: String? = null, data: JSONObject? = null): JSONObject",
    "private suspend fun request(context: Context, path: String, token: String? = null, data: JSONObject? = null): JSONObject",
    "API request signature")
api = replace_one(api,
    'connection.setRequestProperty("Accept", "application/json")',
    'connection.setRequestProperty("Accept", "application/json")\n            connection.setRequestProperty("X-Zent-Device", ZentDeviceId.get(context))',
    "API device-bound header")
api = replace_one(api,
    "suspend fun login(username: String, password: String): String {",
    "suspend fun login(context: Context, username: String, password: String): String {",
    "login signature")
api = replace_one(api,
    'val json = JSONObject().put("username", username).put("password", password)',
    'val json = JSONObject().put("username", username).put("password", password)\n            .put("device_id", ZentDeviceId.get(context))',
    "login request body")
api = replace_one(api, 'val response = request("/api/login", data = json)',
    'val response = request(context, "/api/login", data = json)', "login request")
api = replace_one(api, 'suspend fun me(token: String): ZentAccount {',
    'suspend fun me(context: Context, token: String): ZentAccount {', "me signature")
api = replace_one(api, 'val response = request("/api/me", token)',
    'val response = request(context, "/api/me", token)', "me request")
api = replace_one(api, 'suspend fun logout(token: String) {',
    'suspend fun logout(context: Context, token: String) {', "logout signature")
api = replace_one(api, 'request("/api/logout", token, JSONObject())',
    'request(context, "/api/logout", token, JSONObject())', "logout request")

append_api = '''
    suspend fun fetchUsage(context: Context, token: String): ZentUsageTotals =
        ZentUsageTotals.parse(request(context, "/api/usage", token).getJSONObject("usage"))

    suspend fun uploadUsage(context: Context, token: String, sample: ZentUsageSample): ZentUsageTotals {
        val data = JSONObject()
            .put("epoch", sample.epoch)
            .put("rx_bytes", sample.rxBytes)
            .put("tx_bytes", sample.txBytes)
        return ZentUsageTotals.parse(request(context, "/api/usage", token, data).getJSONObject("usage"))
    }
'''
assert api.rstrip().endswith('}'), "Unexpected API trailing class"
api = api.rstrip()[:-1] + append_api + '''
}

internal data class ZentUsageTotals(
    val rxTotal: Long,
    val txTotal: Long,
    val rxToday: Long,
    val txToday: Long,
    val rxMonth: Long,
    val txMonth: Long,
    val source: String
) {
    companion object {
        fun parse(json: JSONObject) = ZentUsageTotals(
            rxTotal = json.optLong("rx_total", 0L),
            txTotal = json.optLong("tx_total", 0L),
            rxToday = json.optLong("rx_today", 0L),
            txToday = json.optLong("tx_today", 0L),
            rxMonth = json.optLong("rx_month", 0L),
            txMonth = json.optLong("tx_month", 0L),
            source = json.optString("source", "device_estimate")
        )
    }
}
'''

for func in ("login", "me", "logout"):
    old = f"ZentApi.{func}("
    count = ui.count(old)
    if count != 1:
        raise SystemExit(f"Expected one ZentApi.{func} call, found {count}")
    ui = ui.replace(old, f"ZentApi.{func}(context, ", 1)

ui = replace_one(ui,
    '    var statsAvailable by remember { mutableStateOf(true) }',
    '''    var statsAvailable by remember { mutableStateOf(true) }
    val usageTracker = remember(context) { ZentUsageTracker(context) }
    var accountLifetime by remember { mutableStateOf<ZentUsageTotals?>(null) }''',
    "usage state")

effect = '''    // Best-effort persistent traffic accounting. Per-installation counters
    // survive app updates and report with idempotent epochs to the backend.
    LaunchedEffect(token, account?.username, isRunning) {
        val activeUsername = account?.username
        if (token.isNotBlank() && !activeUsername.isNullOrBlank()) {
            val initial = runCatching { ZentApi.fetchUsage(context, token) }.getOrNull()
            if (initial != null) accountLifetime = initial
            while (isActive) {
                if (statsAvailable) {
                    val current = runCatching {
                        usageTracker.sample(activeUsername, isRunning, sessionRx, sessionTx)
                    }.getOrNull()
                    if (current != null) {
                        val sent = runCatching {
                            ZentApi.uploadUsage(context, token, current)
                        }.getOrNull()
                        if (sent != null) accountLifetime = sent
                    }
                }
                delay(30_000L)
            }
        }
    }

'''
ui = replace_one(ui, '    LaunchedEffect(token) {\n        if (token.isNotBlank()) syncProfile(token)',
    effect + '    LaunchedEffect(token) {\n        if (token.isNotBlank()) syncProfile(token)',
    "usage background sync")
ui = replace_one(ui,
    '''                            InfoCard("This VPN session — Total", if (statsAvailable) readableBytes(sessionRx + sessionTx) else "Unavailable")''',
    '''                            InfoCard("This VPN session — Total", if (statsAvailable) readableBytes(sessionRx + sessionTx) else "Unavailable")
                            HorizontalDivider()
                            val local = usageTracker.localTotals(account?.username.orEmpty())
                            val allRx = accountLifetime?.rxTotal ?: local.first
                            val allTx = accountLifetime?.txTotal ?: local.second
                            InfoCard("All time — Download", readableBytes(allRx))
                            InfoCard("All time — Upload", readableBytes(allTx))
                            InfoCard("All time — Total", readableBytes(allRx + allTx))
                            InfoCard("Today (UTC)", accountLifetime?.let {
                                readableBytes(it.rxToday + it.txToday)
                            } ?: "Not synced")
                            InfoCard("This month (UTC)", accountLifetime?.let {
                                readableBytes(it.rxMonth + it.txMonth)
                            } ?: "Not synced")
                            Text("Estimates collected on this phone since v2.7 and synchronized to your account. " +
                                "Not exact 3X-UI server traffic. Existing older usage cannot be reconstructed.",
                                color = Dim, fontSize = 12.sp)''',
    "data usage lifetime display")

assert "ZentDiagnostics" not in ui
assert 'ZentUsageTracker(context)' in ui
assert 'InfoCard("All time — Total"' in ui
assert "ZentApi.login(context, " in ui
api_path.write_text(api, encoding="utf-8")
ui_path.write_text(ui, encoding="utf-8")
helper = Path("scripts/zent-v27/ZentUsageTracker.kt")
assert helper.is_file()
(main/"ZentUsageTracker.kt").write_text(helper.read_text(encoding="utf-8"), encoding="utf-8")
print("Zent Plus v2.7 device binding, lifetime estimates and subscription UI ready.")
