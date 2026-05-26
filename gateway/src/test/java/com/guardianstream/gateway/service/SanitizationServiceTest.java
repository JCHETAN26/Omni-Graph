package com.guardianstream.gateway.service;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class SanitizationServiceTest {

    private final SanitizationService service = new SanitizationService();

    @Test
    @DisplayName("masks a single email address")
    void masksSingleEmail() {
        SanitizationResult result = service.sanitize("Forward the report to ava.patel@guardianstream.dev tonight");

        assertThat(result.sanitizedText()).isEqualTo("Forward the report to [REDACTED_EMAIL] tonight");
        assertThat(result.redactionCount()).isEqualTo(1);
    }

    @Test
    @DisplayName("masks multiple emails and counts each")
    void masksMultipleEmails() {
        SanitizationResult result = service.sanitize("CC alice@example.com and bob@example.com please");

        assertThat(result.sanitizedText()).isEqualTo("CC [REDACTED_EMAIL] and [REDACTED_EMAIL] please");
        assertThat(result.redactionCount()).isEqualTo(2);
    }

    @Test
    @DisplayName("masks SSN in dash-separated format")
    void masksSsn() {
        SanitizationResult result = service.sanitize("Patient SSN is 123-45-6789 on file");

        assertThat(result.sanitizedText()).isEqualTo("Patient SSN is [REDACTED_SSN] on file");
        assertThat(result.redactionCount()).isEqualTo(1);
    }

    @Test
    @DisplayName("does not mask non-SSN digit groups without the standard format")
    void leavesNonSsnDigitsAlone() {
        SanitizationResult result = service.sanitize("Order 12345 received from desk 678");

        assertThat(result.sanitizedText()).isEqualTo("Order 12345 received from desk 678");
        assertThat(result.redactionCount()).isZero();
    }

    @Test
    @DisplayName("masks a Luhn-valid card with no separators")
    void masksLuhnValidCard() {
        SanitizationResult result = service.sanitize("Charge to 4111111111111111 immediately");

        assertThat(result.sanitizedText()).isEqualTo("Charge to [REDACTED_CARD] immediately");
        assertThat(result.redactionCount()).isEqualTo(1);
    }

    @Test
    @DisplayName("masks a Luhn-valid card with space separators")
    void masksLuhnValidCardWithSpaces() {
        SanitizationResult result = service.sanitize("Card 4242 4242 4242 4242 on file");

        assertThat(result.sanitizedText()).isEqualTo("Card [REDACTED_CARD] on file");
        assertThat(result.redactionCount()).isEqualTo(1);
    }

    @Test
    @DisplayName("masks a Luhn-valid card with hyphen separators")
    void masksLuhnValidCardWithHyphens() {
        SanitizationResult result = service.sanitize("Use 5555-5555-5555-4444 for billing");

        assertThat(result.sanitizedText()).isEqualTo("Use [REDACTED_CARD] for billing");
        assertThat(result.redactionCount()).isEqualTo(1);
    }

    @Test
    @DisplayName("leaves a long digit run that fails Luhn untouched")
    void leavesNonLuhnDigitRunAlone() {
        SanitizationResult result = service.sanitize("Order id 1234567890123456 from desk");

        assertThat(result.sanitizedText()).isEqualTo("Order id 1234567890123456 from desk");
        assertThat(result.redactionCount()).isZero();
    }

    @Test
    @DisplayName("leaves a phone-like 10-digit number untouched")
    void leavesPhoneNumberUntouched() {
        SanitizationResult result = service.sanitize("Call me at 5551234567 if blocked");

        assertThat(result.sanitizedText()).isEqualTo("Call me at 5551234567 if blocked");
        assertThat(result.redactionCount()).isZero();
    }

    @Test
    @DisplayName("masks email, SSN, and Luhn-valid card together in one prompt")
    void masksMixedPii() {
        String prompt = "Customer alice@example.com SSN 123-45-6789 card 4111111111111111 thanks";
        SanitizationResult result = service.sanitize(prompt);

        assertThat(result.sanitizedText())
                .isEqualTo("Customer [REDACTED_EMAIL] SSN [REDACTED_SSN] card [REDACTED_CARD] thanks");
        assertThat(result.redactionCount()).isEqualTo(3);
    }

    @Test
    @DisplayName("returns input unchanged when no PII is present")
    void returnsUnchangedWhenClean() {
        SanitizationResult result = service.sanitize("What does Microsoft say about Azure cloud growth?");

        assertThat(result.sanitizedText()).isEqualTo("What does Microsoft say about Azure cloud growth?");
        assertThat(result.redactionCount()).isZero();
    }

    @Test
    @DisplayName("handles empty input")
    void handlesEmptyInput() {
        SanitizationResult result = service.sanitize("");

        assertThat(result.sanitizedText()).isEmpty();
        assertThat(result.redactionCount()).isZero();
    }

    @Test
    @DisplayName("Luhn check rejects strings shorter than 13 digits")
    void luhnRejectsShortStrings() {
        assertThat(SanitizationService.isLuhnValid("411111111111")).isFalse();
    }

    @Test
    @DisplayName("Luhn check rejects strings longer than 19 digits")
    void luhnRejectsLongStrings() {
        assertThat(SanitizationService.isLuhnValid("4111111111111111111111")).isFalse();
    }
}
