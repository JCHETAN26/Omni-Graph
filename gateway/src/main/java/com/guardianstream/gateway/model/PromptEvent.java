package com.guardianstream.gateway.model;

import java.time.Instant;
import java.util.List;

public record PromptEvent(
        String requestId,
        String userId,
        String prompt,
        String sanitizedPrompt,
        int redactionCount,
        List<String> policyTags,
        Instant createdAt
) {
}
