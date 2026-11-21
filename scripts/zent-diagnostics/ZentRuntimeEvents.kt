package com.v2ray.ang.util

import android.content.Context
import java.io.File

/** Minimal, credential-free VPN lifecycle events shared across the app and :daemon processes. */
object ZentRuntimeEvents {
    private const val LOG_FILE = "zent-vpn-runtime-events.txt"
    private val safeEvent = Regex("[A-Z0-9_:-]{1,72}")

    @Synchronized
    fun record(context: Context, event: String) {
        if (!safeEvent.matches(event)) return
        try {
            val file = File(context.filesDir, LOG_FILE)
            val previous = if (file.exists()) file.readLines().takeLast(59) else emptyList()
            val entry = System.currentTimeMillis().toString() + " " + event
            file.writeText((previous + entry).joinToString("\n") + "\n")
        } catch (_: Exception) {
            // Diagnostics must never interfere with VPN startup.
        }
    }

    fun snapshot(context: Context): String = try {
        val file = File(context.filesDir, LOG_FILE)
        if (!file.exists()) "No runtime events yet; reconnect the VPN and rerun diagnostics."
        else file.readLines().takeLast(35).joinToString("\n")
    } catch (_: Exception) {
        "Runtime event log unavailable"
    }
}
