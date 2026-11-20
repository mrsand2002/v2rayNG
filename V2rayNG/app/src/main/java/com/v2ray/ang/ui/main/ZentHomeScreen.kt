package com.v2ray.ang.ui.main

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val Night = Color(0xFF0A1120)
private val Cyan = Color(0xFF38D9E6)
private val Muted = Color(0xFF9AA9BF)

@Composable
fun ZentHomeScreen(
    isRunning: Boolean,
    hasProfile: Boolean,
    onToggleVpn: () -> Unit,
) {
    Surface(modifier = Modifier.fillMaxSize(), color = Night) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 24.dp, vertical = 40.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = "ZENT+",
                    fontSize = 38.sp,
                    fontWeight = FontWeight.Black,
                    color = Cyan,
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(text = "YOUR CONNECTION. SIMPLIFIED.", fontSize = 12.sp, color = Muted)
            }

            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = if (isRunning) "VPN RUNNING" else "VPN STOPPED",
                    color = if (isRunning) Cyan else Color.White,
                    fontSize = 21.sp,
                    fontWeight = FontWeight.Bold,
                )
                Spacer(modifier = Modifier.height(28.dp))
                Button(
                    onClick = onToggleVpn,
                    enabled = isRunning || hasProfile,
                    modifier = Modifier.size(188.dp),
                    shape = CircleShape,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Cyan,
                        contentColor = Night,
                    ),
                ) {
                    Text(
                        text = if (isRunning) "DISCONNECT" else "CONNECT",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                    )
                }
                Spacer(modifier = Modifier.height(22.dp))
                Text(
                    text = if (hasProfile) "VPN profile selected" else "No VPN profile assigned yet",
                    color = Muted,
                    fontSize = 14.sp,
                    textAlign = TextAlign.Center,
                )
            }

            Text(
                text = "Zent Plus • Developer preview",
                color = Muted,
                fontSize = 12.sp,
            )
        }
    }
}
