package scheduler.solver;

import ai.timefold.solver.core.api.score.buildin.hardsoft.HardSoftScore;
import ai.timefold.solver.core.api.score.stream.*;
import scheduler.domain.Talk;

public class Constraints implements ConstraintProvider {
    @Override
    public Constraint[] defineConstraints(ConstraintFactory cf) {
        return new Constraint[] {
            speakerConflict(cf), roomConflict(cf), speakerAvailability(cf),
            trackParallelSessions(cf), flowByLevel(cf), flowByOrder(cf),
            trackRoomConsistency(cf), trackDayConsistency(cf)
        };
    }

    // HARD: Same speaker cannot be in two rooms at the same time
    Constraint speakerConflict(ConstraintFactory cf) {
        return cf.forEachUniquePair(Talk.class, Joiners.equal(Talk::getTimeslot),
                Joiners.filtering((t1, t2) -> hasSpeakerOverlap(t1, t2)))
            .penalize(HardSoftScore.ONE_HARD).asConstraint("Speaker conflict");
    }

    // HARD: Two talks cannot be in the same room at the same time
    Constraint roomConflict(ConstraintFactory cf) {
        return cf.forEachUniquePair(Talk.class, Joiners.equal(Talk::getTimeslot), Joiners.equal(Talk::getRoom))
            .penalize(HardSoftScore.ONE_HARD).asConstraint("Room conflict");
    }

    // HARD: Speaker must be available on the scheduled day
    Constraint speakerAvailability(ConstraintFactory cf) {
        return cf.forEach(Talk.class)
            .filter(t -> t.getTimeslot() != null && !t.getAvailableDays().isEmpty() && !t.isAvailableForTimeslot())
            .penalize(HardSoftScore.ONE_HARD).asConstraint("Speaker availability");
    }

    // SOFT: Prefer not to have the same track in two different rooms at the same time.
    // This is intentionally soft because large conferences (Devoxx, etc.) commonly run
    // parallel sessions within the same track. Making this hard would cause infeasible
    // solutions for any conference with more talks than rooms per track.
    Constraint trackParallelSessions(ConstraintFactory cf) {
        return cf.forEachUniquePair(Talk.class, Joiners.equal(Talk::getTimeslot), Joiners.equal(Talk::getTrackName))
            .penalize(HardSoftScore.ofSoft(3)).asConstraint("Track parallel sessions");
    }

    // SOFT: Beginner → Intermediate → Advanced within a track on the same day
    Constraint flowByLevel(ConstraintFactory cf) {
        return cf.forEachUniquePair(Talk.class, Joiners.equal(Talk::getTrackName))
            .filter((t1, t2) -> t1.getTimeslot() != null && t2.getTimeslot() != null
                && t1.getTimeslot().isSameDay(t2.getTimeslot())
                && ((t1.getTimeslot().compareTo(t2.getTimeslot()) > 0
                    && t1.getAudienceLevel().getDefaultFlowOrder() < t2.getAudienceLevel().getDefaultFlowOrder())
                || (t1.getTimeslot().compareTo(t2.getTimeslot()) < 0
                    && t1.getAudienceLevel().getDefaultFlowOrder() > t2.getAudienceLevel().getDefaultFlowOrder())))
            .penalize(HardSoftScore.ONE_SOFT, (t1, t2) ->
                Math.abs(t1.getAudienceLevel().getDefaultFlowOrder() - t2.getAudienceLevel().getDefaultFlowOrder()))
            .asConstraint("Educational flow by level");
    }

    // SOFT: Respect AI-computed optimal talk sequence within a track
    Constraint flowByOrder(ConstraintFactory cf) {
        return cf.forEachUniquePair(Talk.class, Joiners.equal(Talk::getTrackName))
            .filter((t1, t2) -> t1.getTimeslot() != null && t2.getTimeslot() != null
                && t1.getTimeslot().isSameDay(t2.getTimeslot())
                && ((t1.getTimeslot().compareTo(t2.getTimeslot()) > 0 && t1.getFlowOrder() < t2.getFlowOrder())
                || (t1.getTimeslot().compareTo(t2.getTimeslot()) < 0 && t1.getFlowOrder() > t2.getFlowOrder())))
            .penalize(HardSoftScore.ONE_SOFT, (t1, t2) -> Math.abs(t1.getFlowOrder() - t2.getFlowOrder()))
            .asConstraint("Educational flow by order");
    }

    // SOFT: Keep the same track in the same room on the same day
    Constraint trackRoomConsistency(ConstraintFactory cf) {
        return cf.forEachUniquePair(Talk.class, Joiners.equal(Talk::getTrackName))
            .filter((t1, t2) -> t1.getRoom() != null && t2.getRoom() != null
                && t1.getTimeslot() != null && t2.getTimeslot() != null
                && t1.getTimeslot().isSameDay(t2.getTimeslot()) && !t1.getRoom().equals(t2.getRoom()))
            .penalize(HardSoftScore.ofSoft(1)).asConstraint("Track room consistency");
    }

    // SOFT: Keep the same track on the same day across the whole conference
    Constraint trackDayConsistency(ConstraintFactory cf) {
        return cf.forEachUniquePair(Talk.class, Joiners.equal(Talk::getTrackName))
            .filter((t1, t2) -> t1.getTimeslot() != null && t2.getTimeslot() != null
                && !t1.getTimeslot().isSameDay(t2.getTimeslot()))
            .penalize(HardSoftScore.ofSoft(2)).asConstraint("Track day consistency");
    }

    // Split speaker names on ";" or "," while trimming whitespace.
    // NOTE: Avoid using comma-only split if speaker names may contain commas (e.g. "Smith, John").
    // The Devoxx CSV format uses comma-separated full names (e.g. "Alice,Bob"), so comma splitting
    // is correct here. If your data uses semicolons, switch the separator accordingly.
    private boolean hasSpeakerOverlap(Talk t1, Talk t2) {
        if (t1.getSpeakerNames() == null || t2.getSpeakerNames() == null) return false;
        for (String s1 : t1.getSpeakerNames().split("[,;]"))
            for (String s2 : t2.getSpeakerNames().split("[,;]"))
                if (s1.trim().equalsIgnoreCase(s2.trim())) return true;
        return false;
    }
}
