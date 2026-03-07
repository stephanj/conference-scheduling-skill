package scheduler;

import ai.timefold.solver.core.api.solver.*;
import ai.timefold.solver.core.config.solver.*;
import ai.timefold.solver.core.config.solver.termination.TerminationConfig;
import scheduler.domain.*;
import scheduler.io.*;
import scheduler.solver.Constraints;
import java.nio.file.*;
import java.time.Duration;

public class App {
    public static void main(String[] args) throws Exception {
        if (args.length < 2) { printUsage(); System.exit(1); }
        Path schedulePath = Paths.get(args[0]), talksPath = Paths.get(args[1]);
        Path outputPath = args.length > 2 && !args[2].startsWith("--") ? Paths.get(args[2]) : Paths.get("schedule_output.csv");
        Duration timeLimit = Duration.ofSeconds(30);
        boolean dryRun = false;
        for (String a : args) {
            if (a.startsWith("--time-limit=")) {
                String v = a.substring(13).toLowerCase();
                if (v.endsWith("h"))      timeLimit = Duration.ofHours(Long.parseLong(v.replace("h","")));
                else if (v.endsWith("m")) timeLimit = Duration.ofMinutes(Long.parseLong(v.replace("m","")));
                else                      timeLimit = Duration.ofSeconds(Long.parseLong(v.replace("s","")));
            }
            if (a.equals("--dry-run")) dryRun = true;
        }

        System.out.println("=".repeat(60) + "\nCONFERENCE SCHEDULER - Powered by TimeFold\n" + "=".repeat(60));
        System.out.println("\n📖 Reading input files...");
        CsvReader reader = new CsvReader();
        Schedule problem = reader.readProblem(schedulePath, talksPath);
        long numDays = problem.getTimeslots().stream().map(Timeslot::getDayIndex).distinct().count();
        System.out.printf("   - Days: %d%s%n", numDays, reader.isMultiDay() ? " (" + String.join(", ", reader.getDayNames()) + ")" : "");
        System.out.printf("   - Timeslots: %d%n   - Rooms: %d%n   - Talks: %d%n   - Tracks: %d%n",
            problem.getTimeslots().size(), problem.getRooms().size(), problem.getTalks().size(),
            problem.getTalks().stream().map(Talk::getTrackName).distinct().count());

        int capacity = problem.getTimeslots().size() * problem.getRooms().size();
        if (problem.getTalks().size() > capacity)
            System.err.printf("⚠️  Warning: More talks (%d) than available slots (%d). Some talks will be unscheduled.%n",
                problem.getTalks().size(), capacity);

        if (dryRun) {
            System.out.println("\n✅ Dry-run complete. Input files validated successfully.");
            System.out.printf("   Capacity: %d timeslots × %d rooms = %d slots available for %d talks%n",
                problem.getTimeslots().size(), problem.getRooms().size(), capacity, problem.getTalks().size());
            return;
        }

        System.out.printf("%n⏱️  Solving with time limit: %s%n", formatDuration(timeLimit));
        SolverFactory<Schedule> factory = SolverFactory.create(new SolverConfig()
            .withSolutionClass(Schedule.class).withEntityClasses(Talk.class)
            .withConstraintProviderClass(Constraints.class)
            .withTerminationConfig(new TerminationConfig().withSpentLimit(timeLimit)));
        Solver<Schedule> solver = factory.buildSolver();
        solver.addEventListener(e -> System.out.printf("   New best score: %s%n", e.getNewBestScore()));
        Schedule solution = solver.solve(problem);

        System.out.println("\n✅ Solving complete!\n   Final score: " + solution.getScore());
        CsvWriter writer = new CsvWriter();
        writer.print(solution);
        writer.writeCsv(solution, outputPath);
        System.out.println("\n📄 Schedule written to: " + outputPath);
        Path mdPath = Paths.get(outputPath.toString().replace(".csv", ".md"));
        Files.writeString(mdPath, writer.toMarkdown(solution));
        System.out.println("📄 Markdown written to: " + mdPath);

        long unscheduled = solution.getTalks().stream()
            .filter(t -> t.getTimeslot() == null || t.getRoom() == null).count();
        if (unscheduled > 0)
            System.out.printf("%n⚠️  UNSCHEDULED TALKS: %d (not enough capacity or hard constraint violations)%n", unscheduled);
        if (solution.getScore().hardScore() < 0)
            System.out.println("⚠️  HARD CONSTRAINT VIOLATIONS: " + Math.abs(solution.getScore().hardScore()));
    }

    private static String formatDuration(Duration d) {
        if (d.toHours() > 0) return d.toHours() + "h";
        if (d.toMinutes() > 0) return d.toMinutes() + "m";
        return d.getSeconds() + "s";
    }

    static void printUsage() {
        System.out.println("Usage: java -jar conference-scheduler.jar <schedule.csv> <talks.csv> [output.csv] [--time-limit=30s] [--dry-run]");
        System.out.println("\nTime limit formats: 30s (seconds), 5m (minutes), 1h (hours)");
        System.out.println("--dry-run: Validate input files and show capacity stats without solving");
        System.out.println("\nSchedule CSV: \"from hour\";\"to hour\";\"session type\";\"room name\"");
        System.out.println("Multi-day:    \"day\";\"from hour\";\"to hour\";\"session type\";\"room name\"");
        System.out.println("Talks CSV:    \"Talk ID\";\"Title\";\"Level\";\"Summary\";\"Track\";\"Availability\";...;\"Speakers\"");
        System.out.println("\nNote: Columns 7 (Available from) and 8 (Available to) in the Talks CSV are reserved for future use.");
    }
}
