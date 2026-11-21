#!/usr/bin/env python3
"""Strip test-only runtime events from the stable Zent Plus APK build.

Run after the branded Zent overlay is applied. Keep production VPN startup
and error handling unchanged; only remove the temporary event collector.
Fail closed if the source shape changes.
"""
from pathlib import Path

sources = {
    "V2rayNG/app/src/main/java/com/v2ray/ang/service/CoreVpnService.kt": 9,
    "V2rayNG/app/src/main/java/com/v2ray/ang/service/TProxyService.kt": 4,
    "V2rayNG/app/src/main/java/com/v2ray/ang/core/CoreServiceManager.kt": 2,
}
for filename, expected_calls in sources.items():
    path = Path(filename)
    src = path.read_text(encoding="utf-8")
    assert src.count("import com.v2ray.ang.util.ZentRuntimeEvents") == 1, (
        "ZentRuntimeEvents import missing/duplicated: " + filename
    )
    assert src.count("ZentRuntimeEvents.record(") == expected_calls, (
        "Unexpected runtime event collector calls in " + filename
    )
    output = []
    for line in src.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == "import com.v2ray.ang.util.ZentRuntimeEvents":
            continue
        if stripped.startswith("ZentRuntimeEvents.record(") and stripped.endswith(")"):
            continue
        output.append(line)
    final = "".join(output)
    assert "ZentRuntimeEvents" not in final, "Leftover runtime collector reference: " + filename
    path.write_text(final, encoding="utf-8")

main = Path("V2rayNG/app/src/main/java/com/v2ray/ang/ui/main")
ui = (main / "ZentManagedScreen.kt").read_text(encoding="utf-8")
assert "ZentDiagnostics" not in ui and '"Diagnostics" -> {' not in ui
assert '"Data Usage", "Diagnostics"' not in ui
assert "Server Managed By Mr.මල" in ui
assert "private fun ZentAppearanceCard(" in ui
assert "zent-managed-v4:" in ui
assert not any((main / filename).exists() for filename in (
    "ZentDiagnostics.kt", "ZentSocksProbe.kt", "ZentCoreErrors.kt"
)), "Test-only diagnostic files must not be compiled into the release"
assert not Path("V2rayNG/app/src/main/java/com/v2ray/ang/util/ZentRuntimeEvents.kt").exists()

activity = (main / "MainActivity.kt").read_text(encoding="utf-8")
assert "assigned.copy(verifyPeerCertByName = assigned.server!!.trim())" in activity
assert "assigned.pinnedCA256.isNullOrBlank()" in activity
assert "actual.sni == expected.sni" in activity
assert "PREF_OUTBOUND_DOMAIN_RESOLVE_METHOD, \"0\"" in activity
assert "allowInsecure = true" not in activity

print("CLEAN STABLE RELEASE: diagnostics removed, VPN service retained, SNI/TLS preserved.")
