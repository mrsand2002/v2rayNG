#!/usr/bin/env python3
"""Zent Plus v2.8: clean usage screen, reset and Firebase-free announcements.

Run after the verified v2.7 patch. The VPN engine and security/TLS logic are
not modified. Refuse to patch unknown/changed generated source.
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
        raise SystemExit(f"v2.8 patch: unexpected {label} anchor ({count})")
    return text.replace(old, new, 1)

api_extension = """
    suspend fun resetUsage(context: Context, token: String): ZentUsageTotals =
        ZentUsageTotals.parse(request(context, "/api/usage/reset", token,
            JSONObject().put("confirm", true)).getJSONObject("usage"))

    suspend fun fetchAnnouncements(context: Context, token: String): List<ZentAnnouncement> {
        val array = request(context, "/api/announcements", token).getJSONArray("announcements")
        return (0 until array.length()).map { index ->
            ZentAnnouncement.parse(array.getJSONObject(index))
        }
    }

    suspend fun markAnnouncementRead(context: Context, token: String, id: Int) {
        request(context, "/api/announcements/$id/read", token, JSONObject())
    }
"""
api = replace_one(api, '\n}\n\ninternal data class ZentUsageTotals(',
                  '\n' + api_extension + '}\n\ninternal data class ZentUsageTotals(',
                  "API extensions")
api += """

internal data class ZentAnnouncement(
    val id: Int,
    val title: String,
    val message: String,
    val priority: String,
    val imageBase64: String?,
    val readAt: Long?
) {
    companion object {
        fun parse(json: JSONObject): ZentAnnouncement = ZentAnnouncement(
            id = json.getInt("id"),
            title = json.getString("title"),
            message = json.getString("message"),
            priority = json.optString("priority", "normal"),
            imageBase64 = if (json.isNull("image_base64")) null else json.optString("image_base64", "").takeIf { it.isNotBlank() },
            readAt = if (json.isNull("read_at")) null else json.optLong("read_at")
        )
    }
}
"""
ui = replace_one(ui,
    'listOf("My Profile", "Data Usage", "Settings", "About Zent Plus")',
    'listOf("My Profile", "Data Usage", "Announcements", "Settings", "About Zent Plus")',
    "navigation menu")
ui = replace_one(ui,
    '                        "Data Usage" -> {',
    '''                        "Announcements" -> {
                            PageHeader("Announcements") { page = "Home" }
                            ZentAnnouncementsPage(context, token)
                        }
                        "Data Usage" -> {''', "announcements route")

ui = replace_one(ui,
    '    var accountLifetime by remember { mutableStateOf<ZentUsageTotals?>(null) }',
    '''    var accountLifetime by remember { mutableStateOf<ZentUsageTotals?>(null) }
    var showResetUsageDialog by remember { mutableStateOf(false) }
    var resetUsageBusy by remember { mutableStateOf(false) }
    ZentAnnouncementPopup(context, token)''',
    "announcement popup and reset state")

old_usage = '''                            InfoCard("Data allowance", "Unlimited ∞")
                            InfoCard("This VPN session — Download", if (statsAvailable) readableBytes(sessionRx) else "Unavailable")
                            InfoCard("This VPN session — Upload", if (statsAvailable) readableBytes(sessionTx) else "Unavailable")
                            InfoCard("This VPN session — Total", if (statsAvailable) readableBytes(sessionRx + sessionTx) else "Unavailable")
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
                                color = Dim, fontSize = 12.sp)'''
new_usage = '''                            InfoCard("All-Time Usage", accountLifetime?.let {
                                readableBytes(it.rxTotal + it.txTotal)
                            } ?: "Not synced")
                            InfoCard("Today", accountLifetime?.let {
                                readableBytes(it.rxToday + it.txToday)
                            } ?: "Not synced")
                            InfoCard("This Month", accountLifetime?.let {
                                readableBytes(it.rxMonth + it.txMonth)
                            } ?: "Not synced")
                            Text("Device-estimated usage recorded since v2.7. " +
                                "Not exact server traffic. Resets only change the displayed totals.",
                                color = Dim, fontSize = 12.sp)
                            OutlinedButton(onClick = { showResetUsageDialog = true },
                                enabled = token.isNotBlank() && !resetUsageBusy) {
                                Text("Reset Usage")
                            }
                            if (showResetUsageDialog) {
                                AlertDialog(
                                    onDismissRequest = { if (!resetUsageBusy) showResetUsageDialog = false },
                                    title = { Text("Reset Data Usage?") },
                                    text = { Text("Today, This Month and All-Time Usage will restart from zero. " +
                                        "This does not remove actual VPN server usage, quotas, or subscription access.") },
                                    confirmButton = {
                                        TextButton(enabled = !resetUsageBusy, onClick = {
                                            scope.launch {
                                                resetUsageBusy = true
                                                try {
                                                    val updated = ZentApi.resetUsage(context, token)
                                                    accountLifetime = updated
                                                    showResetUsageDialog = false
                                                    notify("Usage statistics reset", ToastKind.Success)
                                                } catch (e: Exception) {
                                                    notify("Unable to reset usage. Try again.", ToastKind.Error)
                                                } finally { resetUsageBusy = false }
                                            }
                                        }) { Text(if (resetUsageBusy) "Resetting…" else "Reset Usage") }
                                    },
                                    dismissButton = {
                                        TextButton(enabled = !resetUsageBusy,
                                            onClick = { showResetUsageDialog = false }) { Text("Cancel") }
                                    }
                                )
                            }'''
ui = replace_one(ui, old_usage, new_usage, "data usage cleanup")
assert "This VPN session" not in ui[ui.index('"Data Usage" -> {'):ui.index('"Settings" -> {')]
assert 'InfoCard("Today (UTC)"' not in ui
assert 'InfoCard("All time — Download"' not in ui
assert 'ZentAnnouncementPopup(context, token)' in ui
assert 'ZentAnnouncementsPage(context, token)' in ui
assert '"Diagnostics" -> {' not in ui
api_path.write_text(api, encoding="utf-8")
ui_path.write_text(ui, encoding="utf-8")
helper = Path("scripts/zent-v28/ZentAnnouncementsUi.kt")
assert helper.exists()
(main / "ZentAnnouncementsUi.kt").write_text(helper.read_text(encoding="utf-8"),encoding="utf-8")
print("Zent Plus v2.8: announcements/popup, reset usage and streamlined account totals applied.")
