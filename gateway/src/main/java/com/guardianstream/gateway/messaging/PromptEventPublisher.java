package com.guardianstream.gateway.messaging;

import com.guardianstream.gateway.model.PromptEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
public class PromptEventPublisher {

    private static final Logger logger = LoggerFactory.getLogger(PromptEventPublisher.class);

    private final KafkaTemplate<String, PromptEvent> kafkaTemplate;
    private final String topicName;

    public PromptEventPublisher(
            KafkaTemplate<String, PromptEvent> kafkaTemplate,
            @Value("${guardian.kafka.prompt-topic}") String topicName
    ) {
        this.kafkaTemplate = kafkaTemplate;
        this.topicName = topicName;
    }

    public void publish(PromptEvent promptEvent) {
        logger.info("Publishing sanitized prompt event requestId={} topic={}", promptEvent.requestId(), topicName);
        kafkaTemplate.send(topicName, promptEvent.requestId(), promptEvent);
    }
}
