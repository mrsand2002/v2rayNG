package com.v2ray.ang.ui.main

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.os.Build
import com.v2ray.ang.AppConfig
import com.v2ray.ang.handler.MmkvManager
import com.v2ray.ang.handler.SettingsManager
import com.v2ray.ang.util.ZentRuntimeEvents
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.InetSocketAddress
import java.net.Socket
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Privacy-safe, on-device diagnostic checks. No VLESS URI, account token or
 * user credentials are included in reports. Some Android devices prevent
 * VPN-owner applications from issuing a probe through their own VPN network;
 * those results are explicitly INCONCLUSIVE, never reported as a tunnel failure.
 */
internal object ZentDiagnostics {
    suspend fun run(context: Context, vpnUiRunning: Boolean, hasProfile: Boolean): String =
        withContext(Dispatchers.IO) {
            val report = StringBuilder()
            fun line(message: String) { report.appendLine(message) }
            line("Zent Plus • Connection Diagnostics")
            line(SimpleDateFormat("yyyy-MM-dd HH:mm:ss Z", Locale.US).format(Date()))
            line("Android API: ${Build.VERSION.SDK_INT}")
            line("VPN UI state: ${if (vpnUiRunning) "Active" else "Inactive"}")
            line("Managed profile present: ${if (hasProfile) "Yes" else "No"}")
            line("Note: Android VPN active does not guarantee working internet.")
            line("Note: App upload/download counters do not verify tunnel traffic.")
            line("VPN runtime events (Unix millisecond timestamps; newest last):")
            ZentRuntimeEvents.snapshot(context).lineSequence().forEach { line(it) }
            if (MmkvManager.decodeSettingsBool(AppConfig.PREF_DYNAMIC_SOCKS_PORT, false)) {
                line("Local SOCKS listener: INCONCLUSIVE (dynamic port is managed by another process)")
            } else {
                try {
                    Socket().use { socket ->
                        socket.connect(InetSocketAddress("127.0.0.1", SettingsManager.getSocksPort()), 1200)
                    }
                    line("Local SOCKS listener: TCP PORT OPEN (not proof of server access)")
                } catch (e: Exception) {
                    line("Local SOCKS listener: CLOSED OR UNREACHABLE (" + e.javaClass.simpleName + ")")
                }
            }
            line("Xray SOCKS5 outbound HTTPS probe (not routed through Android VPN):")
            if (MmkvManager.decodeSettingsBool(AppConfig.PREF_DYNAMIC_SOCKS_PORT, false)) {
                line("SOCKS5 outbound: INCONCLUSIVE (dynamic port is process-local)")
            } else {
                ZentSocksProbe.run(
                    SettingsManager.getSocksPort(),
                    SettingsManager.getSocksUsername(),
                    SettingsManager.getSocksPassword()
                ).forEach { line(it) }
            }
            val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            if (cm == null) {
                line("Connectivity service: UNAVAILABLE")
                return@withContext report.toString()
            }
            val networks = try { cm.allNetworks.toList() } catch (e: Exception) {
                line("Network inspection: INCONCLUSIVE (${e.javaClass.simpleName})")
                return@withContext report.toString()
            }
            val vpnNetwork: Network? = networks.firstOrNull { network ->
                try {
                    cm.getNetworkCapabilities(network)?.hasTransport(NetworkCapabilities.TRANSPORT_VPN) == true
                } catch (_: Exception) { false }
            }
            if (vpnNetwork == null) {
                line("Android VPN network: NOT FOUND")
                line("Result: VPN interface missing or not visible to this process.")
                return@withContext report.toString()
            }
            line("Android VPN network: PRESENT")
            val caps = cm.getNetworkCapabilities(vpnNetwork)
            line("Android validated internet: ${if (caps?.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED) == true) "YES" else "NO / NOT YET"}")
            line("The checks below are probes, not direct Xray or TUN health readings.")
            try {
                val ips = vpnNetwork.getAllByName("www.gstatic.com")
                line("DNS via VPN network: OK (${ips.size} address(es))")
            } catch (e: Exception) {
                line("DNS via VPN network: FAILED / RESTRICTED (${e.javaClass.simpleName})")
            }
            fun checkHttp(name: String, url: String) {
                try {
                    val connection = vpnNetwork.openConnection(URL(url)) as HttpURLConnection
                    connection.connectTimeout = 6000
                    connection.readTimeout = 6000
                    connection.instanceFollowRedirects = false
                    try {
                        val code = connection.responseCode
                        line("$name: HTTP $code ${if (code in 200..399) "(reachable)" else "(unexpected response)"}")
                    } finally {
                        connection.disconnect()
                    }
                } catch (e: Exception) {
                    line("$name: FAILED / RESTRICTED (${e.javaClass.simpleName})")
                }
            }
            checkHttp("HTTPS via VPN hostname", "https://www.gstatic.com/generate_204")
            checkHttp("HTTPS via VPN IP", "https://1.1.1.1/cdn-cgi/trace")
            line("Interpretation: IP works + hostname fails may indicate DNS.")
            line("Both fail: routing, TUN, Xray, or VPN-owner probe restrictions possible.")
            line("On-device probes cannot definitively prove another app's traffic.")
            report.toString()
        }
}
