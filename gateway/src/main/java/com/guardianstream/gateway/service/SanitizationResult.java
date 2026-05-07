package com.guardianstream.gateway.service;

public record SanitizationResult(
        String sanitizedText,
        int redactionCount
) {
}
