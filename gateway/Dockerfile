FROM maven:3.9.9-eclipse-temurin-21

WORKDIR /workspace

COPY pom.xml .
RUN mvn -q dependency:go-offline

COPY src ./src

EXPOSE 8080

CMD ["mvn", "spring-boot:run"]
