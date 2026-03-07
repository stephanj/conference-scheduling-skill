package scheduler.io;

import com.opencsv.*;
import com.opencsv.exceptions.CsvValidationException;
import scheduler.domain.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.stream.Collectors;

public class CsvReader {
    private List<String> dayNames = new ArrayList<>();

    public Schedule readProblem(Path schedulePath, Path talksPath) throws IOException, CsvValidationException {
        List<Timeslot> timeslots = readSchedule(schedulePath);
        List<Room> rooms = extractRooms(schedulePath);
        List<Talk> talks = readTalks(talksPath);
        if (!dayNames.isEmpty()) {
            for (Talk t : talks) {
                if (t.getAvailableDaysRaw() != null && !t.getAvailableDaysRaw().isBlank())
                    t.parseAvailableDays(t.getAvailableDaysRaw(), dayNames);
            }
        }
        return new Schedule(timeslots, rooms, talks);
    }

    public List<Timeslot> readSchedule(Path path) throws IOException, CsvValidationException {
        Set<Timeslot> slots = new LinkedHashSet<>();
        Map<String, Integer> dayMap = new LinkedHashMap<>();
        try (CSVReader r = csv(path)) {
            String[] h = r.readNext();
            boolean hasDay = h != null && h.length > 0 && clean(h[0]).toLowerCase().contains("day");
            int dayCol = hasDay ? 0 : -1, fromCol = hasDay ? 1 : 0, toCol = hasDay ? 2 : 1;
            String[] line;
            while ((line = r.readNext()) != null) {
                if (line.length < (hasDay ? 3 : 2)) continue;
                String dayName = null;
                int dayIdx = 0;
                if (hasDay) {
                    dayName = clean(line[dayCol]);
                    if (!dayMap.containsKey(dayName)) dayMap.put(dayName, dayMap.size());
                    dayIdx = dayMap.get(dayName);
                }
                slots.add(Timeslot.fromCsv(clean(line[fromCol]), clean(line[toCol]), dayIdx, dayName));
            }
        }
        dayNames = new ArrayList<>(dayMap.keySet());
        List<Timeslot> list = new ArrayList<>(slots);
        Collections.sort(list);
        return list;
    }

    public List<Room> extractRooms(Path path) throws IOException, CsvValidationException {
        Set<String> names = new LinkedHashSet<>();
        try (CSVReader r = csv(path)) {
            String[] h = r.readNext();
            boolean hasDay = h != null && h.length > 0 && clean(h[0]).toLowerCase().contains("day");
            int roomCol = hasDay ? 4 : 3;
            String[] line;
            while ((line = r.readNext()) != null) {
                if (line.length > roomCol) {
                    String name = clean(line[roomCol]);
                    if (!name.isBlank()) names.add(name);
                }
            }
        }
        return names.stream().map(Room::new).sorted(Comparator.comparing(Room::getName)).collect(Collectors.toList());
    }

    /**
     * Reads talks from CSV. Column mapping:
     *   0: Talk ID
     *   1: Talk Title
     *   2: Audience Level (BEGINNER / INTERMEDIATE / ADVANCED)
     *   3: Talk Summary
     *   4: Track Name
     *   5: Speaker Availability days (e.g. "Wednesday,Thursday" or "1,2" or empty = all days)
     *   6: Available from  — reserved for future use, currently ignored
     *   7: Available to    — reserved for future use, currently ignored
     *   8: Speaker names (comma-separated)
     */
    public List<Talk> readTalks(Path path) throws IOException, CsvValidationException {
        List<Talk> talks = new ArrayList<>();
        try (CSVReader r = csv(path)) {
            r.skip(1);
            String[] line;
            while ((line = r.readNext()) != null) {
                if (line.length >= 9) {
                    Talk t = new Talk(clean(line[0]), clean(line[1]), clean(line[3]), clean(line[4]),
                        AudienceLevel.fromString(clean(line[2])), clean(line[8]));
                    t.setAvailableDaysRaw(clean(line[5]));
                    talks.add(t);
                }
            }
        }
        return talks;
    }

    /**
     * Applies AI-computed flow order to talks. Call this after readTalks() and before solving.
     *
     * The flowOrders map key is the track name; the value is an ordered list of talk IDs
     * representing the optimal educational sequence (first ID = should be scheduled earliest).
     *
     * Example:
     *   Map<String, List<String>> flowOrders = new HashMap<>();
     *   flowOrders.put("Java", List.of("4945", "4931", "4929", "5456", "5261"));
     *   reader.applyFlowOrder(talks, flowOrders);
     */
    public void applyFlowOrder(List<Talk> talks, Map<String, List<String>> flowOrders) {
        Map<String, Integer> idToOrder = new HashMap<>();
        for (Map.Entry<String, List<String>> entry : flowOrders.entrySet()) {
            List<String> ids = entry.getValue();
            for (int i = 0; i < ids.size(); i++) {
                idToOrder.put(ids.get(i).trim(), i + 1);
            }
        }
        for (Talk t : talks) {
            Integer order = idToOrder.get(t.getId());
            if (order != null) t.setFlowOrder(order);
        }
    }

    public List<String> getDayNames() { return dayNames; }
    public boolean isMultiDay() { return dayNames.size() > 1; }

    private CSVReader csv(Path p) throws IOException {
        return new CSVReaderBuilder(Files.newBufferedReader(p))
            .withCSVParser(new CSVParserBuilder().withSeparator(';').withQuoteChar('"').build()).build();
    }
    private String clean(String v) { return v == null ? "" : v.trim().replaceAll("^\"|\"$", ""); }
}
