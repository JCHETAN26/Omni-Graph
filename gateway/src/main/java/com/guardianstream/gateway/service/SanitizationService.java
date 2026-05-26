package com.guardianstream.gateway.service;

import org.springframework.stereotype.Service;

import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class SanitizationService {

    private static final Pattern EMAIL_PATTERN =
            Pattern.compile("\\b[\\w._%+-]+@[\\w.-]+\\.[A-Za-z]{2,}\\b");
    private static final Pattern SSN_PATTERN =
            Pattern.compile("\\b\\d{3}-\\d{2}-\\d{4}\\b");
    // Candidate card runs: 13–19 digits, optionally separated by space or hyphen.
    // Each candidate is Luhn-validated before redaction to avoid masking phone
    // numbers, order ids, or other long digit runs.
    private static final Pattern CARD_CANDIDATE_PATTERN =
            Pattern.compile("(?<!\\d)(?:\\d[ \\-]?){12,18}\\d(?!\\d)");

    private static final List<PatternReplacement> SIMPLE_PATTERNS = List.of(
            new PatternReplacement(EMAIL_PATTERN, "[REDACTED_EMAIL]"),
            new PatternReplacement(SSN_PATTERN, "[REDACTED_SSN]")
    );

    public SanitizationResult sanitize(String prompt) {
        String sanitized = prompt;
        int totalRedactions = 0;

        for (PatternReplacement patternReplacement : SIMPLE_PATTERNS) {
            ReplaceResult result = replaceAll(sanitized, patternReplacement.pattern(), patternReplacement.replacement());
            sanitized = result.text();
            totalRedactions += result.count();
        }

        ReplaceResult cardResult = replaceCards(sanitized);
        sanitized = cardResult.text();
        totalRedactions += cardResult.count();

        return new SanitizationResult(sanitized, totalRedactions);
    }

    private ReplaceResult replaceAll(String input, Pattern pattern, String replacement) {
        Matcher matcher = pattern.matcher(input);
        StringBuffer buffer = new StringBuffer();
        int count = 0;
        while (matcher.find()) {
            count++;
            matcher.appendReplacement(buffer, Matcher.quoteReplacement(replacement));
        }
        matcher.appendTail(buffer);
        return new ReplaceResult(buffer.toString(), count);
    }

    private ReplaceResult replaceCards(String input) {
        Matcher matcher = CARD_CANDIDATE_PATTERN.matcher(input);
        StringBuffer buffer = new StringBuffer();
        int count = 0;
        while (matcher.find()) {
            String candidate = matcher.group();
            String digitsOnly = candidate.replaceAll("[ \\-]", "");
            if (isLuhnValid(digitsOnly)) {
                count++;
                matcher.appendReplacement(buffer, Matcher.quoteReplacement("[REDACTED_CARD]"));
            } else {
                matcher.appendReplacement(buffer, Matcher.quoteReplacement(candidate));
            }
        }
        matcher.appendTail(buffer);
        return new ReplaceResult(buffer.toString(), count);
    }

    static boolean isLuhnValid(String digits) {
        int len = digits.length();
        if (len < 13 || len > 19) {
            return false;
        }
        int sum = 0;
        boolean doubleDigit = false;
        for (int i = len - 1; i >= 0; i--) {
            char ch = digits.charAt(i);
            if (ch < '0' || ch > '9') {
                return false;
            }
            int digit = ch - '0';
            if (doubleDigit) {
                digit *= 2;
                if (digit > 9) {
                    digit -= 9;
                }
            }
            sum += digit;
            doubleDigit = !doubleDigit;
        }
        return sum % 10 == 0;
    }

    private record PatternReplacement(Pattern pattern, String replacement) {
    }

    private record ReplaceResult(String text, int count) {
    }
}
