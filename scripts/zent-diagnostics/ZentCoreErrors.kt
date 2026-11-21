package com.v2ray.ang.ui.main

import java.util.concurrent.TimeUnit

/**
 * Read Xray's own recent GoLog warning/error lines, report error categories
 * only. NEVER copy native log lines, which may contain private server addresses,
 * UUIDs or hostnames.
 */
internal object ZentCoreErrors {
    fun summarize(): List<String> {
        return try {
            val process = ProcessBuilder(
                "logcat", "-d", "-t", "600", "-v", "brief", "-s", "GoLog:W"
            ).redirectErrorStream(true).start()
            val lines = process.inputStream.bufferedReader().use {
                it.lineSequence().take(1500).toList()
            }
            if (!process.waitFor(3, TimeUnit.SECONDS)) process.destroyForcibly()
            val log = lines.filter {
                it.contains("GoLog") &&
                (it.contains("failed", ignoreCase = true) ||
                 it.contains("error", ignoreCase = true) ||
                 it.contains("eof", ignoreCase = true) ||
                 it.contains("handshake", ignoreCase = true))
            }.takeLast(150)
            if (log.isEmpty()) {
                return listOf("Recent Xray errors: NOT OBSERVED (GoLog may be unavailable)")
            }
            val categories = linkedMapOf(
                "CERTIFICATE_OR_NAME_REJECTED" to listOf(
                    "failed to verify certificate", "x509:", "certificate is valid for",
                    "certificate signed by unknown", "peer cert is invalid",
                    "invalid certificate", "tls: bad certificate"
                ),
                "SERVER_TLS_HANDSHAKE" to listOf(
                    "failed to dial tls", "tls handshake", "handshake failure",
                    "tls: first record", "remote error: tls"
                ),
                "VLESS_HANDSHAKE" to listOf(
                    "failed to read response header", "failed to decode response",
                    "invalid response version", "vless/outbound", "vless: "
                ),
                "REMOTE_TCP_OR_DNS" to listOf(
                    "connection refused", "connection reset", "network is unreachable",
                    "no route to host", "i/o timeout", "no such host", "dial tcp"
                ),
                "REMOTE_CLOSED_EARLY" to listOf(
                    "unexpected eof", "connection ends", "eof",
                    "connection closed", "broken pipe"
                )
            )
            val results = mutableListOf("Recent Xray warning/error entries observed: " + log.size)
            categories.forEach { (label, patterns) ->
                val matching = log.count { line ->
                    patterns.any { phrase -> line.contains(phrase, ignoreCase = true) }
                }
                if (matching > 0) results.add("Xray error category $label: $matching")
            }
            if (results.size == 1) {
                results.add("Xray errors: OTHER (no recognizable category)")
            }
            results.add("Xray log contents withheld to protect server credentials")
            results
        } catch (e: Exception) {
            listOf("Xray log classification: UNAVAILABLE (" + e.javaClass.simpleName + ")")
        }
    }
}
