package com.guardianstream.gateway.service;

import org.springframework.stereotype.Service;

import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class SanitizationService {

    private static final List<PatternReplacement> PATTERNS = List.of(
            new PatternReplacement(Pattern.compile("\\b[\\w._%+-]+@[\\w.-]+\\.[A-Za-z]{2,}\\b"), "[REDACTED_EMAIL]"),
            new PatternReplacement(Pattern.compile("\\b\\d{3}-\\d{2}-\\d{4}\\b"), "[REDACTED_SSN]"),
            new PatternReplacement(Pattern.compile("\\b(?:\\d[ -]*?){13,16}\\b"), "[REDACTED_CARD]")
    );

    public SanitizationResult sanitize(String prompt) {
        String sanitized = prompt;
        int totalRedactions = 0;

        for (PatternReplacement patternReplacement : PATTERNS) {
            Matcher matcher = patternReplacement.pattern().matcher(sanitized);
            int matches = 0;
            StringBuffer buffer = new StringBuffer();

            while (matcher.find()) {
                matches++;
                matcher.appendReplacement(buffer, patternReplacement.replacement());
            }

            matcher.appendTail(buffer);
            sanitized = buffer.toString();
            totalRedactions += matches;
        }

        return new SanitizationResult(sanitized, totalRedactions);
    }

    private record PatternReplacement(Pattern pattern, String replacement) {
    }
}
