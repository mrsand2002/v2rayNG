package com.v2ray.ang.ui.main

import android.content.Context
import android.os.SystemClock
import kotlin.math.abs

/**
 * UI session clock for the VPN-connected state.
 *
 * Uses monotonic elapsedRealtime so minimizing/recreating the Activity does
 * not reset the displayed session timer. It tracks only the VPN state observed
 * by ZentManagedScreen; server-side 3X-UI state is authoritative for traffic.
 */
internal object ZentSessionClock {
    internal data class Start(val startedElapsedMs: Long, val rxAtStart: Long, val txAtStart: Long)

    private const val NAME = "zent_v281_session_state"
    private const val MAX_BOOT_CLOCK_SKEW_MS = 180_000L

    @Synchronized
    fun resume(context: Context, currentRx: Long, currentTx: Long): Start {
        val prefs = context.applicationContext.getSharedPreferences(NAME, Context.MODE_PRIVATE)
        val elapsed = SystemClock.elapsedRealtime()
        val estimatedBoot = System.currentTimeMillis() - elapsed
        val oldStarted = prefs.getLong("started_elapsed", -1L)
        val oldBoot = prefs.getLong("boot_wall", Long.MIN_VALUE)
        val oldRx = prefs.getLong("rx_start", -1L)
        val oldTx = prefs.getLong("tx_start", -1L)
        // Restart when Android has rebooted, when counters rolled back, or
        // after a fresh explicit connect has cleared this state.
        val valid = prefs.getBoolean("active", false) &&
            oldStarted in 1L..elapsed &&
            oldBoot != Long.MIN_VALUE &&
            abs(estimatedBoot - oldBoot) <= MAX_BOOT_CLOCK_SKEW_MS &&
            (currentRx < 0L || oldRx < 0L || currentRx >= oldRx) &&
            (currentTx < 0L || oldTx < 0L || currentTx >= oldTx)
        if (valid) return Start(oldStarted, oldRx, oldTx)
        check(prefs.edit().putBoolean("active", true)
            .putLong("started_elapsed", elapsed)
            .putLong("boot_wall", estimatedBoot)
            .putLong("rx_start", currentRx)
            .putLong("tx_start", currentTx)
            .commit()) { "Unable to persist session start" }
        return Start(elapsed, currentRx, currentTx)
    }

    @Synchronized
    fun reset(context: Context) {
        val prefs = context.applicationContext.getSharedPreferences(NAME, Context.MODE_PRIVATE)
        prefs.edit().clear().commit()
    }
}
