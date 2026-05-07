package com.guardianstream.gateway.service;

import com.guardianstream.gateway.api.PromptRequest;
import com.guardianstream.gateway.api.PromptResponse;
import com.guardianstream.gateway.messaging.PromptEventPublisher;
import com.guardianstream.gateway.model.PromptEvent;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Service
public class PromptIngressService {

    private final SanitizationService sanitizationService;
    private final PromptEventPublisher promptEventPublisher;

    public PromptIngressService(
            SanitizationService sanitizationService,
            PromptEventPublisher promptEventPublisher
    ) {
        this.sanitizationService = sanitizationService;
        this.promptEventPublisher = promptEventPublisher;
    }

    public PromptResponse ingest(PromptRequest request) {
        SanitizationResult sanitizationResult = sanitizationService.sanitize(request.prompt());
        String requestId = UUID.randomUUID().toString();
        Instant createdAt = Instant.now();
        List<String> policyTags = List.of("sanitized");

        PromptEvent event = new PromptEvent(
                requestId,
                request.userId(),
                request.prompt(),
                sanitizationResult.sanitizedText(),
                sanitizationResult.redactionCount(),
                policyTags,
                createdAt
        );

        promptEventPublisher.publish(event);

        return new PromptResponse(
                requestId,
                sanitizationResult.sanitizedText(),
                sanitizationResult.redactionCount(),
                policyTags,
                createdAt,
                "accepted"
        );
    }
}
