# Delegation boundary

Exercise 2. Scenario: Thursday 29 Oct 2026, 7:20 am, at home in Ulm. Data:
`https://jhbelz.github.io/agentic-interaction-data/v1`.

**alone**: the agent acts and reports afterwards. **approval**: the agent asks first and acts
only after a yes.

| # | Action | Tool | Decision | Justification |
|---|---|---|---|---|
| 1 | Read the appointments of a day | `calendar(date)` | alone | Only reads, changes nothing and reaches no one. It is the basis of almost every answer; a question before it would only slow the agent down. |
| 2 | Look up the weather | `weather(city, date)` | alone | Read-only public information without side effects. In the role play, nobody expected a question here. |
| 3 | Search train connections | `connections(from, to, date)` | alone | Searching is not booking: it costs nothing and commits to nothing. The agent needs the results to propose anything sensible. |
| 4 | Read notes | `notes()`, `note(id)` | alone | The notes are my own and reading them sends nothing anywhere. They held facts the calendar lacks (15 minutes for the visitor pass, the travel cost rule, where absences are announced). |
| 5 | Create a personal block in the calendar (e.g. travel time, no other attendees) | `create_event(...)` | alone | It only touches my own calendar, notifies nobody and is undone by deleting the block. The agent reports it afterwards, so I see it anyway. |
| 6 | Reschedule an appointment with other attendees | `reschedule_event(...)` | approval | It changes other people's calendars and sends them notifications. A wrong change costs other people time and cannot be quietly taken back. |
| 7 | Book a train ticket | `book_ticket(train)` | approval | It spends money, saver fares cost a cancellation fee, and the choice of train depends on priorities only I know (buffer time, departure time, price). That the travel policy allows tickets up to 50 € without pre-registration is my employer's rule, not my consent. |
| 8 | Send a message to third parties | `send_message(to, text)` | approval | The message speaks in my name and cannot be unsent. Recipient and wording have to be right; in the role play the recipient was not even in the calendar. |
| 9 | Create a note | `create_note(...)` | alone | It only adds something private: nothing is lost, nobody else sees it, and it can be deleted again. |
| 10 | Delete a note | `delete_note(id)` | approval | It cannot be undone, because the tools have no trash. A vague order like "tidy up" does not show which note is really obsolete. |

## My rule

The agent acts alone as long as an action only reads or adds something that only I see and that
can be undone without loss, and asks first as soon as it costs money, reaches other people or
cannot be undone.

## Observations from the role play

1. **Questions before reading are unnecessary.** On card A the agent asked "Should I look up train
   connections?" before a pure read. The delegating person marked it as an unnecessary question:
   it only cost time. Reading (actions 1–4) is therefore alone.
2. **Personal blocks were never missed as a question.** The travel blocks on cards B and C were
   entered without asking and reported afterwards. The delegating person did not miss a question
   there.
3. **Missing information was named, not guessed.** The walking time from Munich main station to
   Werk 2 and an online link for the stand-up are not in the data. The agent said so instead of
   making them up.
