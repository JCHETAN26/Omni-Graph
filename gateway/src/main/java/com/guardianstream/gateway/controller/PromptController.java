package com.guardianstream.gateway.controller;

import com.guardianstream.gateway.api.PromptRequest;
import com.guardianstream.gateway.api.PromptResponse;
import com.guardianstream.gateway.service.PromptIngressService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/prompts")
public class PromptController {

    private final PromptIngressService promptIngressService;

    public PromptController(PromptIngressService promptIngressService) {
        this.promptIngressService = promptIngressService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.ACCEPTED)
    public PromptResponse ingest(@Valid @RequestBody PromptRequest request) {
        return promptIngressService.ingest(request);
    }
}
