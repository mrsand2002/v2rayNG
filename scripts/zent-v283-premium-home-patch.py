#!/usr/bin/env python3
"""Zent Plus v2.8.3: premium Home screen, no VPN engine/service changes.

Apply after the verified 2.8.1 UI/session patch. This is deliberately
constrained to the customer Home screen and UID speed telemetry already
collected every two seconds. Reject unexpected generated source shapes.
"""
from pathlib import Path

ui_path = Path("V2rayNG/app/src/main/java/com/v2ray/ang/ui/main/ZentManagedScreen.kt")
src = ui_path.read_text(encoding="utf-8")

def replace_one(old, new, label):
    global src
    count = src.count(old)
    if count != 1:
        raise SystemExit(f"Zent v2.8.3: expected 1 {label} anchor, found {count}")
    src = src.replace(old, new, 1)

replace_one(
    "import android.net.TrafficStats\n",
    "import android.net.TrafficStats\n"
    "import androidx.compose.foundation.Canvas\n"
    "import androidx.compose.animation.core.animateDpAsState\n"
    "import androidx.compose.ui.draw.shadow\n"
    "import androidx.compose.ui.geometry.Offset\n"
    "import androidx.compose.ui.graphics.Path\n"
    "import androidx.compose.ui.graphics.drawscope.Stroke\n",
    "premium UI imports"
)

replace_one(
    '''    var rxSpeed by remember { mutableLongStateOf(0L) }
    var txSpeed by remember { mutableLongStateOf(0L) }''',
    '''    var rxSpeed by remember { mutableLongStateOf(0L) }
    var txSpeed by remember { mutableLongStateOf(0L) }
    // In-memory chart only: 32 samples x 2 seconds. No telemetry or permission change.
    val downloadSamples = remember { mutableStateListOf<Long>() }
    val uploadSamples = remember { mutableStateListOf<Long>() }''',
    "two existing speed counters"
)

replace_one(
    '''                rxSpeed = rx * 1000 / elapsed
                txSpeed = tx * 1000 / elapsed''',
    '''                rxSpeed = rx * 1000 / elapsed
                txSpeed = tx * 1000 / elapsed
                downloadSamples.add(rxSpeed.coerceAtLeast(0L))
                uploadSamples.add(txSpeed.coerceAtLeast(0L))
                if (downloadSamples.size > 32) downloadSamples.removeAt(0)
                if (uploadSamples.size > 32) uploadSamples.removeAt(0)''',
    "sample graph with existing UID data"
)

replace_one(
    '''            rxSpeed = 0
            txSpeed = 0
            uptimeMs = 0''',
    '''            rxSpeed = 0
            txSpeed = 0
            downloadSamples.clear()
            uploadSamples.clear()
            uptimeMs = 0''',
    "clear chart when VPN service stops"
)

replace_one(
    '''                                Text(when {
                                    isRunning -> "VPN SERVICE ACTIVE"''',
    '''                                val haloElevation by animateDpAsState(
                                    targetValue = if (isRunning) 15.dp else 1.dp,
                                    label = "zent_connection_halo"
                                )
                                Text("PRIVATE CONNECTION",
                                    color = Dim, fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold)
                                Text(when {
                                    isRunning -> "VPN SERVICE ACTIVE"''',
    "premium connection heading and animated halo"
)

replace_one(
    '''                                }, modifier = Modifier.size(186.dp), shape = CircleShape, enabled = !busy,
                                    colors = ButtonDefaults.buttonColors(containerColor = Cyan,''',
    '''                                }, modifier = Modifier
                                    .size(180.dp)
                                    .shadow(
                                        haloElevation, CircleShape,
                                        ambientColor = Cyan.copy(alpha = 0.36f),
                                        spotColor = Cyan.copy(alpha = 0.45f)
                                    )
                                    .border(
                                        if (isRunning) 3.dp else 1.dp,
                                        if (isRunning) Cyan.copy(alpha = 0.68f)
                                        else Dim.copy(alpha = 0.3f), CircleShape
                                    ),
                                    shape = CircleShape, enabled = !busy,
                                    colors = ButtonDefaults.buttonColors(containerColor = Cyan,''',
    "premium button preserving existing onClick and VPN actions"
)

replace_one(
    '''                                StatCard("Session traffic", if (statsAvailable) readableBytes(sessionRx + sessionTx) else "Unavailable", Modifier.weight(1f))
                            }
                        }
                        "My Profile" -> {''',
    '''                                StatCard("Session traffic", if (statsAvailable) readableBytes(sessionRx + sessionTx) else "Unavailable", Modifier.weight(1f))
                            }
                            Spacer(Modifier.height(10.dp))
                            ZentPremiumTrafficGraph(
                                isRunning = isRunning,
                                statsAvailable = statsAvailable,
                                darkMode = darkMode,
                                downloadSamples = downloadSamples,
                                uploadSamples = uploadSamples
                            )
                        }
                        "My Profile" -> {''',
    "Home-only activity graph insertion"
)

src += r'''

/** Lightweight on-device activity chart. Not exact Xray/3X-UI traffic. */
@Composable
private fun ZentPremiumTrafficGraph(
    isRunning: Boolean,
    statsAvailable: Boolean,
    darkMode: Boolean,
    downloadSamples: List<Long>,
    uploadSamples: List<Long>
) {
    val bg = if (darkMode) Color(0xFF132A3E) else Color(0xFFEDF5FB)
    val label = if (darkMode) Color(0xFFA8BDCF) else Color(0xFF557085)
    val uploadColor = Color(0xFFE8A56B)
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = bg,
        shape = RoundedCornerShape(20.dp)
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(11.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text("NETWORK ACTIVITY",
                    color = label, fontSize = 12.sp,
                    fontWeight = FontWeight.Bold)
                Text(
                    when {
                        !isRunning -> "OFFLINE"
                        !statsAvailable -> "UNAVAILABLE"
                        else -> "LIVE · ~1 MIN"
                    },
                    color = label, fontSize = 10.sp
                )
            }
            Canvas(modifier = Modifier.fillMaxWidth().height(90.dp)) {
                val gridColor = label.copy(alpha = 0.16f)
                for (step in 1..3) {
                    val y = size.height * step / 4f
                    drawLine(gridColor, Offset(0f, y),
                        Offset(size.width, y), strokeWidth = 1.dp.toPx())
                }
                if (isRunning && statsAvailable) {
                    val largest = maxOf(
                        1024L, downloadSamples.maxOrNull() ?: 0L,
                        uploadSamples.maxOrNull() ?: 0L
                    ).toFloat()
                    fun historyPath(samples: List<Long>): Path {
                        val path = Path()
                        if (samples.size < 2) return path
                        samples.takeLast(32).forEachIndexed { index, value ->
                            val x = index.toFloat() / 31f * size.width
                            val y = size.height * (
                                1f - (value.toFloat() / largest).coerceIn(0f, 1f)
                            )
                            if (index == 0) path.moveTo(x, y)
                            else path.lineTo(x, y)
                        }
                        return path
                    }
                    if (downloadSamples.size > 1) {
                        drawPath(historyPath(downloadSamples), color = Cyan,
                            style = Stroke(width = 2.5.dp.toPx()))
                    }
                    if (uploadSamples.size > 1) {
                        drawPath(historyPath(uploadSamples), color = uploadColor,
                            style = Stroke(width = 2.dp.toPx()))
                    }
                }
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(22.dp)
            ) {
                Text("● Download", color = Cyan, fontSize = 12.sp)
                Text("● Upload", color = uploadColor, fontSize = 12.sp)
            }
            Text("Live device estimate · Not exact server traffic",
                color = label, fontSize = 10.sp)
        }
    }
}
'''

assert src.count("ZentPremiumTrafficGraph(") == 2
assert 'Server Managed By Mr.මල' in src
assert 'ZentSessionClock.resume(context, previousRx, previousTx)' in src
assert 'ZentApi.uploadUsage(context, token, current)' in src
assert 'ZentAnnouncementPopup(context, token)' in src
assert '"Announcements" -> {' not in src
assert 'allowInsecure = true' not in src
ui_path.write_text(src, encoding="utf-8")
print("Zent Plus v2.8.3 premium home applied; VPN action/state, login and backend are unchanged.")
