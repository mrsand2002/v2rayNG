#!/usr/bin/env python3
"""Patch the v2.2 overlay into Zent Plus v2.3 before building the signed APK.
Only customer-facing label and appearance selector are changed.
"""
from pathlib import Path

path = Path("zent/android/ZentManagedScreen.kt")
src = path.read_text(encoding="utf-8")

def replace_one(before, after):
    global src
    if src.count(before) != 1:
        raise SystemExit("Unexpected v2.2 source, refusing to patch: " + before[:55])
    src = src.replace(before, after, 1)

replace_one(
    "import androidx.compose.animation.AnimatedVisibility\n",
    "import androidx.compose.animation.AnimatedVisibility\nimport androidx.compose.animation.animateColorAsState\n"
)
replace_one(
    "import androidx.compose.foundation.background\n",
    "import androidx.compose.foundation.background\nimport androidx.compose.foundation.border\nimport androidx.compose.foundation.BorderStroke\n"
)
replace_one("server managed by Mr.මල", "Server Managed By Mr.මල")

start_marker = '                            listOf(\n                                "system" to "Follow System",'
end_marker = "                            HorizontalDivider()"
if src.count(start_marker) != 1:
    raise SystemExit("Cannot find the old appearance selector")
start = src.index(start_marker)
end = src.index(end_marker, start)
if "RadioButton(" not in src[start:end]:
    raise SystemExit("Unexpected appearance selector structure")
new_selector = '''                            Text("Choose how Zent Plus looks", color = Dim, fontSize = 12.sp)
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                listOf(
                                    Triple("light", "Light", "☀"),
                                    Triple("dark", "Dark", "☾"),
                                    Triple("system", "System", "◐")
                                ).forEach { (mode, label, icon) ->
                                    ZentAppearanceCard(
                                        title = label,
                                        icon = icon,
                                        selected = appearanceMode == mode,
                                        onClick = {
                                            appearanceMode = mode
                                            prefs.edit().putString("appearance_mode", mode).apply()
                                        },
                                        modifier = Modifier.weight(1f)
                                    )
                                }
                            }
'''
src = src[:start] + new_selector + src[end:]
if "private fun ZentAppearanceCard(" in src:
    raise SystemExit("Appearance card already exists")

src += '''
/** Compact, animated theme selector. No Material icons dependency required. */
@Composable
private fun ZentAppearanceCard(
    title: String,
    icon: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val outline by animateColorAsState(
        targetValue = if (selected) Cyan else Dim.copy(alpha = 0.32f),
        label = "appearance_outline"
    )
    val fill by animateColorAsState(
        targetValue = if (selected) Cyan.copy(alpha = 0.13f) else Panel,
        label = "appearance_fill"
    )
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(16.dp))
            .background(fill)
            .border(BorderStroke(if (selected) 2.dp else 1.dp, outline), RoundedCornerShape(16.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 6.dp, vertical = 14.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(7.dp)
    ) {
        Text(icon, color = Cyan, fontSize = 27.sp, textAlign = TextAlign.Center)
        Text(title, color = Ink, fontWeight = FontWeight.SemiBold,
            fontSize = 12.sp, maxLines = 1, textAlign = TextAlign.Center)
        Text(if (selected) "✓ Selected" else "Select", color = if (selected) Cyan else Dim,
            fontSize = 10.sp, maxLines = 1, textAlign = TextAlign.Center)
    }
}
'''
path.write_text(src, encoding="utf-8")
print("Zent Plus v2.3 UI patched successfully")
