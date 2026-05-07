package com.guardianstream.gateway.api;

import jakarta.validation.constraints.NotBlank;

public record PromptRequest(
        @NotBlank String userId,
        @NotBlank String prompt
) {
}
