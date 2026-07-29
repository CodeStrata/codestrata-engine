plugins {
    java
    id("org.springframework.boot") version "3.3.0"
}

dependencies {
    implementation("org.springframework.boot:spring-boot-starter:3.3.0")
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.2")
    implementation(project(":shared"))
}
