package com.v2ray.ang.ui.main

import android.content.Context
import android.graphics.BitmapFactory
import android.util.Base64
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Non-Firebase customer announcements. The existing API provides authenticated,
 * audience-filtered messages and read receipts. No Android notification permission.
 */
@Composable
internal fun ZentAnnouncementPopup(context: Context, token: String) {
    var notices by remember(token) { mutableStateOf<List<ZentAnnouncement>>(emptyList()) }
    var popupShown by remember(token) { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(token) {
        if (token.isBlank()) {
            notices = emptyList()
            return@LaunchedEffect
        }
        while (isActive) {
            runCatching { ZentApi.fetchAnnouncements(context, token) }.onSuccess { notices = it }
            delay(60_000L)
        }
    }
    val pending = if (popupShown) null else notices.firstOrNull { it.readAt == null }
    if (token.isNotBlank() && pending != null) {
        fun dismiss() {
            popupShown = true
            notices = notices.map { if (it.id == pending.id) it.copy(readAt = System.currentTimeMillis() / 1000) else it }
            scope.launch {
                runCatching { ZentApi.markAnnouncementRead(context, token, pending.id) }
            }
        }
        AlertDialog(
            onDismissRequest = { dismiss() },
            title = { Text(pending.title) },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    Text(pending.message)
                    if (pending.imageBase64 != null) {
                        Spacer(Modifier.height(12.dp))
                        ZentAnnouncementImage(pending.imageBase64)
                    }
                }
            },
            confirmButton = { TextButton(onClick = { dismiss() }) { Text("Got it") } }
        )
    }
}

@Composable
internal fun ZentAnnouncementsPage(context: Context, token: String) {
    var notices by remember(token) { mutableStateOf<List<ZentAnnouncement>>(emptyList()) }
    var refreshing by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(token) {
        if (token.isNotBlank()) {
            refreshing = true
            runCatching { ZentApi.fetchAnnouncements(context, token) }.onSuccess { notices = it }
            refreshing = false
        } else notices = emptyList()
    }
    Column(modifier = Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Announcements", fontWeight = FontWeight.Bold)
        Text("Messages from the Zent Plus team. New announcements appear when the app connects to the internet.")
        Button(
            enabled = !refreshing && token.isNotBlank(),
            onClick = {
                scope.launch {
                    refreshing = true
                    runCatching { ZentApi.fetchAnnouncements(context, token) }.onSuccess { notices = it }
                    refreshing = false
                }
            }
        ) { Text(if (refreshing) "Refreshing…" else "Refresh") }
        if (token.isBlank()) Text("Sign in to see announcements.")
        else if (notices.isEmpty() && !refreshing) Text("No announcements right now.")
        notices.forEach { item ->
            HorizontalDivider()
            Text(item.title, fontWeight = FontWeight.SemiBold)
            Text(item.message)
            if (item.imageBase64 != null) ZentAnnouncementImage(item.imageBase64)
            if (item.readAt == null) {
                TextButton(onClick = {
                    notices = notices.map { if (it.id == item.id) it.copy(readAt = System.currentTimeMillis() / 1000) else it }
                    scope.launch { runCatching { ZentApi.markAnnouncementRead(context, token, item.id) } }
                }) { Text("Mark as read") }
            } else Text("Read")
        }
    }
}

/** Bound untrusted raster dimensions before allocating a decoded bitmap. */
@Composable
private fun ZentAnnouncementImage(encoded: String) {
    val bitmap = remember(encoded) {
        runCatching {
            val data = Base64.decode(encoded, Base64.DEFAULT)
            if (data.isEmpty() || data.size > 180_000) return@runCatching null
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(data, 0, data.size, bounds)
            if (bounds.outWidth !in 1..2048 || bounds.outHeight !in 1..2048) return@runCatching null
            BitmapFactory.decodeByteArray(data, 0, data.size)?.asImageBitmap()
        }.getOrNull()
    }
    if (bitmap != null) {
        Image(bitmap = bitmap, contentDescription = "Announcement image",
            modifier = Modifier.fillMaxWidth().heightIn(max = 260.dp),
            contentScale = ContentScale.Fit)
    }
}
