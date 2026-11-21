#!/usr/bin/env python3
"""Apply managed-profile correctness fixes to the existing Zent Plus build overlay.

Fail closed on source mismatch. Do not embed customer VLESS URI or credentials.
"""
from pathlib import Path

apply_path = Path("zent/github/apply_zent.py")
src = apply_path.read_text(encoding="utf-8")
old = '''            onApplyProfile = { uri ->
                val newGuid = withContext(Dispatchers.IO) {
                    val before = MmkvManager.decodeAllServerList().toSet()
                    val result = AngConfigManager.importBatchConfig(uri, "", false).first
                    if (result != 1) null else {
                        val all = MmkvManager.decodeAllServerList()
                        (all.filter { it !in before } + all.filter { it in before }).firstOrNull { guid ->
                            MmkvManager.decodeServerConfig(guid)?.configType == EConfigType.VLESS
                        }
                    }
                }
                if (newGuid != null) {
                    mainViewModel.updateSelectedGuid(newGuid)'''
new = '''            onApplyProfile = { uri ->
                val newGuid = withContext(Dispatchers.IO) {
                    // The imported profile MUST match the centrally assigned URI.
                    // Old behavior could select an unrelated older VLESS server.
                    val expected = runCatching {
                        com.v2ray.ang.fmt.VlessFmt.parse(uri)
                    }.getOrNull()
                    if (expected == null || expected.server.isNullOrBlank() ||
                        expected.password.isNullOrBlank() ||
                        (expected.serverPort?.toIntOrNull() ?: 0) !in 1..65535
                    ) {
                        null
                    } else {
                        val count = AngConfigManager.importBatchConfig(uri, "", false).first
                        if (count != 1) null else {
                            MmkvManager.decodeServerList("").firstOrNull { guid ->
                                val actual = MmkvManager.decodeServerConfig(guid)
                                actual != null &&
                                    actual.configType == EConfigType.VLESS &&
                                    actual.password == expected.password &&
                                    actual.server == expected.server &&
                                    actual.serverPort == expected.serverPort &&
                                    actual.network == expected.network &&
                                    actual.security == expected.security &&
                                    actual.sni == expected.sni &&
                                    actual.fingerPrint == expected.fingerPrint &&
                                    actual.alpn == expected.alpn &&
                                    actual.flow == expected.flow
                            }
                        }
                    }
                }
                if (newGuid != null) {
                    // Avoid pinning a dynamic DNS endpoint to a stale pre-resolved IP.
                    // This preserves the actual host and lets the Xray DNS resolver work.
                    MmkvManager.encodeSettings(AppConfig.PREF_OUTBOUND_DOMAIN_RESOLVE_METHOD, "0")
                    mainViewModel.updateSelectedGuid(newGuid)'''
assert src.count(old) == 1, "Unexpected MainActivity overlay import block"
src = src.replace(old, new, 1)
apply_path.write_text(src, encoding="utf-8")

screen = Path("zent/android/ZentManagedScreen.kt")
src = screen.read_text(encoding="utf-8")
old_marker = 'val marker = "zent-managed-v2:'
new_marker = 'val marker = "zent-managed-v3:'
assert src.count(old_marker) == 1, "Unexpected managed profile revision marker"
src = src.replace(old_marker, new_marker, 1)
screen.write_text(src, encoding="utf-8")

print("Managed VLESS import now selects exact assigned profile; avoids stale DNS IP pinning.")
