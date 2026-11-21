package com.v2ray.ang.ui.main

import android.content.Context
import android.provider.Settings
import java.util.UUID

/** Android app/signing-key scoped ID survives normal reinstalls on the same user profile.
 * Android does not provide an unfalsifiable device identity to ordinary apps.
 */
internal object ZentDeviceId {
    fun get(context: Context): String {
        val id = Settings.Secure.getString(
            context.contentResolver, Settings.Secure.ANDROID_ID
        )?.lowercase().orEmpty()
        require(Regex("^[a-f0-9]{16}$").matches(id)) {
            "Device identifier unavailable. Check your Android profile."
        }
        return id
    }
}

internal data class ZentUsageSample(
    val epoch: String,
    val rxBytes: Long,
    val txBytes: Long
)

/**
 * Device-side, best-effort VPN traffic estimates with durable monotonically
 * increasing counters. Backend de-duplicates reports using installation epoch.
 * It is NOT authoritative 3X-UI/Xray server accounting.
 */
internal class ZentUsageTracker(context: Context) {
    private val prefs = context.getSharedPreferences("zent_usage_v27", Context.MODE_PRIVATE)

    @Synchronized
    fun sample(username: String, connected: Boolean, rx: Long, tx: Long): ZentUsageSample {
        require(username.matches(Regex("^[A-Za-z0-9_.-]{3,40}$")))
        val key = "account_" + username.lowercase() + "_"
        val epoch = prefs.getString(key + "epoch", null)
            .takeUnless { it.isNullOrBlank() }
            ?: UUID.randomUUID().toString().replace("-", "")
        val previousOwner = prefs.getString("last_active_user", null)
        val lastActive = prefs.getBoolean("last_active", false) && previousOwner == username
        val lastRx = prefs.getLong(key + "last_rx", 0)
        val lastTx = prefs.getLong(key + "last_tx", 0)
        val accumulatedRx = prefs.getLong(key + "total_rx", 0)
        val accumulatedTx = prefs.getLong(key + "total_tx", 0)
        val liveRx = rx.coerceAtLeast(0)
        val liveTx = tx.coerceAtLeast(0)

        // The existing session counters reset on a disconnect or core restart.
        // A decrease is treated as a fresh session, not as negative traffic.
        val deltaRx = if (!connected) 0 else if (!lastActive || liveRx < lastRx) liveRx else liveRx - lastRx
        val deltaTx = if (!connected) 0 else if (!lastActive || liveTx < lastTx) liveTx else liveTx - lastTx
        val totalRx = (accumulatedRx + deltaRx).coerceAtLeast(accumulatedRx)
        val totalTx = (accumulatedTx + deltaTx).coerceAtLeast(accumulatedTx)

        val saved = prefs.edit()
            .putString(key + "epoch", epoch)
            .putLong(key + "total_rx", totalRx)
            .putLong(key + "total_tx", totalTx)
            .putLong(key + "last_rx", if (connected) liveRx else 0L)
            .putLong(key + "last_tx", if (connected) liveTx else 0L)
            .putString("last_active_user", if (connected) username else null)
            .putBoolean("last_active", connected)
            .commit()
        check(saved) { "Cannot persist VPN data usage counters" }
        return ZentUsageSample(epoch, totalRx, totalTx)
    }

    fun localTotals(username: String): Pair<Long,Long> {
        val key = "account_" + username.lowercase() + "_"
        return prefs.getLong(key + "total_rx", 0L) to prefs.getLong(key + "total_tx", 0L)
    }
}
