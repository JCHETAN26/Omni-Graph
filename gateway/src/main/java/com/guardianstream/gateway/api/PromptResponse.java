package com.guardianstream.gateway.api;

import java.time.Instant;
import java.util.List;

public record PromptResponse(
        String requestId,
        String sanitizedPrompt,
        int redactionCount,
        List<String> policyTags,
        Instant createdAt,
        String status
) {
}
