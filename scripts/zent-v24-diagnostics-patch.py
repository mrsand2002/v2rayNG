#!/usr/bin/env python3
"""Apply the Zent Plus on-device Diagnostics screen after extracting v2.3 overlay."""
from pathlib import Path
src_path = Path("zent/android/ZentManagedScreen.kt")
src = src_path.read_text(encoding="utf-8")

def replace_once(old, new, label):
    global src
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"Unexpected signed v2.3 overlay ({label}: {n} matches)")
    src = src.replace(old, new, 1)

replace_once(
    "import android.content.Intent\n",
    "import android.content.Intent\nimport android.content.ClipData\nimport android.content.ClipboardManager\n",
    "clipboard imports",
)
replace_once(
    "    var checkingVersion by remember { mutableStateOf(false) }",
    """    var checkingVersion by remember { mutableStateOf(false) }
    var diagnosticReport by remember { mutableStateOf("Press Run Diagnostics while the VPN is connected.") }
    var diagnosticBusy by remember { mutableStateOf(false) }""",
    "diagnostic state",
)
replace_once(
    'listOf("My Profile", "Data Usage", "Settings", "About Zent Plus")',
    'listOf("My Profile", "Data Usage", "Diagnostics", "Settings", "About Zent Plus")',
    "drawer navigation",
)
needle='''                        "Settings" -> {
                            PageHeader("Settings") { page = "Home" }'''
insert='''                        "Diagnostics" -> {
                            PageHeader("Connection Diagnostics") { page = "Home" }
                            InfoCard("VPN service", if (isRunning) "Active — connectivity not verified" else "Disconnected")
                            Text("This screen tests what Android can observe. A connected icon or moving speed counter is not proof that WhatsApp and websites work.",
                                color = Dim, fontSize = 13.sp)
                            Button(
                                onClick = {
                                    scope.launch {
                                        diagnosticBusy = true
                                        diagnosticReport = "Running connection diagnostics…"
                                        try {
                                            diagnosticReport = ZentDiagnostics.run(context, isRunning, hasLocalProfile)
                                        } catch (ex: Exception) {
                                            diagnosticReport = "Diagnostics unavailable: \${ex.javaClass.simpleName}"
                                        } finally { diagnosticBusy = false }
                                    }
                                },
                                enabled = !diagnosticBusy,
                                modifier = Modifier.fillMaxWidth()
                            ) { Text(if (diagnosticBusy) "TESTING…" else "RUN DIAGNOSTICS") }
                            if (diagnosticBusy) LinearProgressIndicator(Modifier.fillMaxWidth())
                            Text(diagnosticReport, color = Ink, fontSize = 12.sp,
                                modifier = Modifier.fillMaxWidth().background(Panel, RoundedCornerShape(12.dp)).padding(14.dp))
                            OutlinedButton(onClick = {
                                val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                                clipboard?.setPrimaryClip(ClipData.newPlainText("Zent Plus diagnostics", diagnosticReport))
                                notify(if (clipboard != null) "Diagnostic report copied" else "Clipboard unavailable")
                            }, enabled = !diagnosticBusy, modifier = Modifier.fillMaxWidth()) {
                                Text("COPY REPORT")
                            }
                            Text("No passwords, tokens or VLESS links are included. Review your report before sharing.",
                                color = Dim, fontSize = 11.sp)
                        }
                        "Settings" -> {
                            PageHeader("Settings") { page = "Home" }'''
# Fix literal Kotlin interpolation placeholder in our Python triple-quoted source.
insert=insert.replace("\\\${ex.javaClass.simpleName}", "${ex.javaClass.simpleName}")
replace_once(needle,insert,"diagnostic screen")
src_path.write_text(src, encoding="utf-8")
dest=Path("V2rayNG/app/src/main/java/com/v2ray/ang/ui/main")
dest.mkdir(parents=True,exist_ok=True)
(dest/"ZentDiagnostics.kt").write_text(Path("scripts/zent-diagnostics/ZentDiagnostics.kt").read_text(encoding="utf-8"),encoding="utf-8")
print("Zent Plus v2.4 Diagnostics UI patch ready.")
