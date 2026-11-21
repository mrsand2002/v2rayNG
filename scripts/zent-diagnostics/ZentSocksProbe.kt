package com.v2ray.ang.ui.main

import java.io.BufferedReader
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.InputStreamReader
import java.net.InetSocketAddress
import java.net.Socket
import javax.net.ssl.SSLSocket
import javax.net.ssl.SSLSocketFactory

/**
 * Checks actual HTTPS through Xray's SOCKS listener, independent of Android
 * VPN-owner network probing. Never includes the profile URI or credentials in a report.
 */
internal object ZentSocksProbe {
    private const val HOST = "www.gstatic.com"
    private const val PORT = 443

    fun run(socksPort: Int, username: String?, password: String?): List<String> {
        val lines = mutableListOf<String>()
        var stage = "LOCAL_SOCKS_CONNECTION"
        try {
            Socket().use { socket ->
                socket.soTimeout = 6500
                socket.connect(InetSocketAddress("127.0.0.1", socksPort), 2500)
                val input = DataInputStream(socket.getInputStream())
                val output = DataOutputStream(socket.getOutputStream())

                stage = "SOCKS5_HANDSHAKE"
                val hasCredentials = !username.isNullOrEmpty() && !password.isNullOrEmpty()
                if (hasCredentials) {
                    output.write(byteArrayOf(5, 2, 0, 2))
                } else {
                    output.write(byteArrayOf(5, 1, 0))
                }
                output.flush()
                val version = input.readUnsignedByte()
                val method = input.readUnsignedByte()
                if (version != 5 || method == 255) {
                    lines.add("SOCKS5 handshake: REJECTED")
                    return@use
                }
                when (method) {
                    0 -> Unit
                    2 -> {
                        if (!hasCredentials) {
                            lines.add("SOCKS5 authentication: REQUIRED BUT NOT AVAILABLE")
                            return@use
                        }
                        val user = username!!.toByteArray(Charsets.UTF_8)
                        val pass = password!!.toByteArray(Charsets.UTF_8)
                        if (user.size !in 1..255 || pass.size !in 1..255) {
                            lines.add("SOCKS5 authentication: INVALID CREDENTIAL LENGTH")
                            return@use
                        }
                        output.writeByte(1)
                        output.writeByte(user.size)
                        output.write(user)
                        output.writeByte(pass.size)
                        output.write(pass)
                        output.flush()
                        val authVersion = input.readUnsignedByte()
                        val authStatus = input.readUnsignedByte()
                        if (authVersion != 1 || authStatus != 0) {
                            lines.add("SOCKS5 authentication: FAILED")
                            return@use
                        }
                    }
                    else -> {
                        lines.add("SOCKS5 handshake: UNSUPPORTED AUTH METHOD")
                        return@use
                    }
                }
                lines.add("SOCKS5 handshake: OK")

                stage = "SOCKS5_REMOTE_CONNECT"
                val domain = HOST.toByteArray(Charsets.US_ASCII)
                output.write(byteArrayOf(5, 1, 0, 3))
                output.writeByte(domain.size)
                output.write(domain)
                output.writeShort(PORT)
                output.flush()

                val replyVersion = input.readUnsignedByte()
                val reply = input.readUnsignedByte()
                input.readUnsignedByte() // reserved
                val addressType = input.readUnsignedByte()
                if (replyVersion != 5 || reply != 0) {
                    lines.add("SOCKS5 remote TCP: FAILED (reply code $reply)")
                    return@use
                }
                val addressLength = when (addressType) {
                    1 -> 4
                    3 -> input.readUnsignedByte()
                    4 -> 16
                    else -> throw IllegalStateException("Unexpected SOCKS address type")
                }
                input.readFully(ByteArray(addressLength))
                input.readUnsignedShort() // bound port
                lines.add("SOCKS5 remote TCP: CONNECTED")

                stage = "HTTPS_TLS_HANDSHAKE"
                val factory = SSLSocketFactory.getDefault() as SSLSocketFactory
                val tls = factory.createSocket(socket, HOST, PORT, false) as SSLSocket
                tls.use {
                    it.soTimeout = 6500
                    val params = it.sslParameters
                    params.endpointIdentificationAlgorithm = "HTTPS"
                    it.sslParameters = params
                    it.startHandshake()
                    lines.add("SOCKS5 HTTPS TLS: OK")

                    stage = "HTTPS_HTTP_RESPONSE"
                    it.outputStream.write(
                        ("GET /generate_204 HTTP/1.1\r\nHost: $HOST\r\nConnection: close\r\n\r\n")
                            .toByteArray(Charsets.US_ASCII)
                    )
                    it.outputStream.flush()
                    val status = BufferedReader(
                        InputStreamReader(it.inputStream, Charsets.US_ASCII)
                    ).readLine()
                    val httpCode = status?.split(" ")?.getOrNull(1)?.toIntOrNull()
                    lines.add(
                        if (httpCode != null && httpCode in 200..399)
                            "SOCKS5 HTTPS: SUCCESS (HTTP $httpCode)"
                        else "SOCKS5 HTTPS: UNEXPECTED RESPONSE"
                    )
                }
            }
        } catch (e: Exception) {
            lines.add("SOCKS5 probe: FAILED at $stage (" + e.javaClass.simpleName + ")")
        }
        return lines
    }
}
