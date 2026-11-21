#!/usr/bin/env python3
"""Patch Zent Plus v2.3 overlay for offline-first customer connections.

Run AFTER extracting zent-v23-overlay.zip and BEFORE zent/github/apply_zent.py.
This is source preparation for the NEXT signed Android release. It does not
publish or sign an APK and must be reviewed alongside the stable backend URL.
"""
from pathlib import Path

path = Path("zent/android/ZentManagedScreen.kt")
src = path.read_text(encoding="utf-8")

def replace_once(before: str, after: str, label: str) -> None:
    global src
    count = src.count(before)
    if count != 1:
        raise SystemExit(f"Unexpected Zent v2.3 source ({label}: {count} matches)")
    src = src.replace(before, after, 1)

replace_once(
    """    var token by remember { mutableStateOf(vault.read().orEmpty()) }
    var username by remember { mutableStateOf("") }""",
    """    val restoredToken = remember { vault.read().orEmpty() }
    var token by remember { mutableStateOf(restoredToken) }
    // Cache account status separately from the encrypted login token.
    // Offline reconnect is allowed only for a previously verified, unexpired account.
    val cachedAccount = remember(restoredToken) {
        val cachedUsername = prefs.getString("cached_username", "").orEmpty()
        if (restoredToken.isBlank() || cachedUsername.isBlank()) null else {
            val expiry = prefs.getLong("cached_expiry_seconds", Long.MIN_VALUE)
                .takeUnless { it == Long.MIN_VALUE }
            ZentAccount(
                username = cachedUsername,
                active = prefs.getBoolean("cached_active", false) &&
                    (expiry == null || expiry > System.currentTimeMillis() / 1000),
                expirySeconds = expiry,
                revision = prefs.getInt("cached_revision", 0),
                vlessUri = null
            )
        }
    }
    var username by remember { mutableStateOf("") }""",
    "restore cached account"
)
replace_once(
    """    var account by remember { mutableStateOf<ZentAccount?>(null) }""",
    """    var account by remember { mutableStateOf<ZentAccount?>(cachedAccount) }""",
    "restore account state"
)
replace_once(
    """    var profileReady by remember { mutableStateOf(hasLocalProfile) }""",
    """    var profileReady by remember { mutableStateOf(hasLocalProfile && cachedAccount?.active == true) }""",
    "gate cached profile"
)
replace_once(
    """    var connecting by remember { mutableStateOf(false) }""",
    """    var connecting by remember { mutableStateOf(false) }
    val vpnIsRunning by rememberUpdatedState(isRunning)""",
    "read live VPN state in coroutine"
)
replace_once(
    """            } else profileReady = true
        } catch (ex: Exception) {""",
    """            } else profileReady = true
            // Only a successful server validation can refresh cached authorization.
            // This metadata contains no token or VPN server credentials.
            prefs.edit()
                .putString("cached_username", fetched.username)
                .putBoolean("cached_active", fetched.active)
                .putLong("cached_expiry_seconds", fetched.expirySeconds ?: Long.MIN_VALUE)
                .putInt("cached_revision", fetched.revision)
                .apply()
        } catch (ex: Exception) {""",
    "cache online verification"
)
replace_once(
    """            if (err.contains("Login required", true) || err.contains("account expired", true)) {
                if (isRunning) onStopVpn()
                onClearProfile()
                vault.clear()
                token = ""
                profileReady = false
                account = null
            }""",
    """            if (err.contains("Login required", true) ||
                err.contains("account expired", true) ||
                err.contains("Account inactive or expired", true)) {
                // A confirmed server-side rejection revokes the local profile.
                // Network errors and temporary outages never wipe the offline cache.
                if (vpnIsRunning) onStopVpn()
                onClearProfile()
                vault.clear()
                prefs.edit()
                    .remove("cached_username")
                    .remove("cached_active")
                    .remove("cached_expiry_seconds")
                    .remove("cached_revision")
                    .remove("applied_marker")
                    .apply()
                appliedMarker = ""
                token = ""
                profileReady = false
                account = null
            }""",
    "reject only confirmed invalid session"
)
replace_once(
    """    LaunchedEffect(token) {
        if (token.isNotBlank()) syncProfile(token)
    }
    LaunchedEffect(token) {
        if (token.isNotBlank()) while (isActive) {
            delay(120_000)
            syncProfile(token)
        }
    }
    LaunchedEffect(token) {
        if (token.isNotBlank()) {
            val info = runCatching { ZentVersionCheck.latest() }.getOrNull()""",
    """    // Do not require an internet request just to show the saved Connect button.
    // First login / legacy installs still need one successful online profile sync.
    LaunchedEffect(token) {
        if (token.isNotBlank() && (!profileReady || !hasLocalProfile || account == null)) {
            syncProfile(token)
        }
    }
    LaunchedEffect(token) {
        if (token.isNotBlank()) while (isActive) {
            delay(5 * 60_000)
            // Once VPN is running, refresh entitlement and server config through it.
            if (vpnIsRunning) syncProfile(token)
        }
    }
    LaunchedEffect(token, isRunning) {
        if (token.isNotBlank() && isRunning) {
            val info = runCatching { ZentVersionCheck.latest() }.getOrNull()""",
    "no pre-VPN recurring API calls"
)
replace_once(
    """                    prefs.edit().remove("applied_marker").apply()""",
    """                    prefs.edit()
                        .remove("applied_marker")
                        .remove("cached_username")
                        .remove("cached_active")
                        .remove("cached_expiry_seconds")
                        .remove("cached_revision")
                        .apply()""",
    "clear saved entitlement on sign out"
)
replace_once(
    """                                    val session = ZentApi.login(username.trim(), password)
                                    vault.save(session)
                                    password = ""
                                    token = session""",
    """                                    val signedInUsername = username.trim()
                                    val session = ZentApi.login(signedInUsername, password)
                                    // Never reuse a previous customer's locally stored VLESS profile.
                                    if (prefs.getString("cached_username", "") != signedInUsername) {
                                        if (vpnIsRunning) onStopVpn()
                                        onClearProfile()
                                        prefs.edit()
                                            .remove("applied_marker")
                                            .remove("cached_username")
                                            .remove("cached_active")
                                            .remove("cached_expiry_seconds")
                                            .remove("cached_revision")
                                            .apply()
                                        appliedMarker = ""
                                        profileReady = false
                                        account = null
                                    }
                                    vault.save(session)
                                    password = ""
                                    token = session""",
    "isolate account switches"
)
replace_once(
    """                                        account?.active != true -> notify("Account not active", ToastKind.Error)""",
    """                                        account?.active != true ||
                                            account?.expirySeconds?.let { it <= System.currentTimeMillis() / 1000 } == true ->
                                                notify("Account expired or not verified", ToastKind.Error)""",
    "check locally cached expiry"
)
path.write_text(src, encoding="utf-8")
print("Zent Plus offline-first source patch applied.")
