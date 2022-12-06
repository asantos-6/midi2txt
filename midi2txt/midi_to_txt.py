from mido import MidiFile
# we use our own bpm2tempo becaus the mido stuff cuts off decimals - which is not good when the bpm tempo is not an int
from midi2txt import bpm2tempo, calc_beat_times
import argparse
import os
import copy


def midi_to_txt(input_file, bpm=120, calc_beats=False):

    times = []
    max_time = 0

    infile = MidiFile(input_file)
    ppq = infile.ticks_per_beat

    midi_tempo = bpm2tempo(bpm)
    s_per_tick = midi_tempo / 1000.0 / 1000 / ppq

    file_type = infile.type

    tempo_track = []

    for track_idx, track in enumerate(infile.tracks):
        cur_time = 0
        if file_type == 1 and len(infile.tracks) > 1:  # if we only got one track, we should not skip it and it should contain all events
            if track_idx == 0:  # store track 0 as tempo track
                tempo_track = track
                continue
            else:
                # merge tempo track into current track
                tempo_idx = 0
                track_idx = 0

                cur_track = []
                while tempo_idx < len(tempo_track) or track_idx < len(track):
                    if tempo_idx >= len(tempo_track):
                        cur_track.append(track[track_idx])
                        track_idx += 1
                        continue
                    if track_idx >= len(track):
                        cur_track.append(tempo_track[tempo_idx])
                        tempo_idx += 1
                        continue
                    if tempo_track[tempo_idx].time <= track[track_idx].time:
                        cur_track.append(tempo_track[tempo_idx])
                        track[track_idx].time -= tempo_track[tempo_idx].time
                        tempo_idx += 1
                    else:
                        cur_track.append(track[track_idx])
                        tempo_track[tempo_idx].time -= track[track_idx].time
                        track_idx += 1
        else:
            cur_track = track

        for message in cur_track:
            delta_tick = message.time
            delta_time = delta_tick * s_per_tick
            cur_time += delta_time

            if cur_time > max_time:  # collect max time for beats if necessary
                max_time = cur_time

            if message.type == 'set_tempo':
                midi_tempo = message.tempo
                s_per_tick = midi_tempo / 1000.0 / 1000 / ppq

            if message.type == 'note_on' and message.velocity > 0:
                inst_idx = message.note
                velocity = message.velocity  # float(message.velocity) / 127.0
                times.append([cur_time, cur_time, inst_idx, velocity])

            if message.type == 'note_off' or (hasattr(message, 'velocity') and message.velocity == 0):
                inst_idx = message.note
                found_on = False
                for i in reversed(range(len(times))):
                    if times[i][2] == inst_idx:
                        if times[i][0] == times[i][1]:
                            times[i][1] = cur_time
                            found_on = True
                            break
                if not found_on:
                    print("Orphaned note_off event: %3.5f \t %d " % (cur_time, inst_idx))

    if calc_beats:
        beat_times = calc_beat_times(copy.deepcopy(infile.tracks[0]), max_time, ppq)
    else:
        beat_times = None

    return times, beat_times


def write_output(times, beat_times, output_file, beats_file=None, write_beats=False, offset=0, input_file=None, offsets=False):
    assert os.path.isfile(input_file)
    in_file_path = os.path.dirname(input_file)
    if output_file is None:
        output_file = in_file_path
    if os.path.isdir(output_file):
        out_file_path = output_file
        in_file_name = os.path.basename(input_file)
        file_name_wo_ext, _ = os.path.splitext(in_file_name)
        output_file = os.path.join(out_file_path, file_name_wo_ext + ".txt")
    else:
        out_file_path = os.path.dirname(output_file)

    assert os.path.isdir(out_file_path)
    out_file_name = os.path.basename(output_file)
    out_file_name_wo_ext, _ = os.path.splitext(out_file_name)

    if beats_file is None:
        beats_file = os.path.join(out_file_path, out_file_name_wo_ext + ".beats")

    # sort by time (for multiple tracks)
    times.sort(key=lambda tup: tup[0])
    with open(output_file, 'w') as f:
        for entry in times:
            if offsets:
                f.write("%.5f %.5f %d %d \n" % (entry[0] + offset, entry[1] + offset, entry[2], entry[3]))
                if entry[0] == entry[1]:
                    print("no offset found for event: %3.5f %d" % (entry[0]+ offset, entry[2]))
            else:
                f.write("%.5f %d %d \n" % (entry[0]+offset, entry[2], entry[3]))

    if write_beats:
        with open(beats_file, 'w') as f:
            for entry in beat_times:
                f.write("%3.5f \t %d\n" % (entry[0]+offset, entry[1]))


def main():
    # add argument parser
    parser = argparse.ArgumentParser(
        description='Convert midi annotations for drum files to txt.')
    parser.add_argument('--infile', '-i', help='input file name.')
    parser.add_argument('--outfile', '-o', help='output file name.', default=None)
    parser.add_argument('--time_offset', '-m', help='offset for time of labels.', default=0, type=float)
    parser.add_argument('--tempo', '-t', help='Tempo to be used (in BPM) if MIDI file doesn\'t contain tempo events.',
                        default=120, type=float)
    parser.add_argument('--beatsout', '-b', help='Write beats files.', action='store_true')
    parser.add_argument('--offsets', '-f', help='Write offset timestamps.', action='store_true')

    args = parser.parse_args()
    input_file = args.infile
    output_file = args.outfile
    offset = args.time_offset
    bpm_param = args.tempo
    write_beats = args.beatsout
    offsets = args.offsets

    if os.path.isdir(input_file):
        in_files = os.listdir(input_file)
        in_files = [os.path.join(input_file, cur_file) for cur_file in in_files if cur_file.endswith('.mid') and not cur_file.startswith('._')]
        assert output_file is None or os.path.isdir(output_file)
    else:
        in_files = input_file

    for cur_file in in_files:
        print("Reading midi file '" + cur_file + "' ...")
        times, beat_times = midi_to_txt(cur_file, bpm_param, write_beats)
        print("Writing output ...")
        write_output(times, beat_times, output_file, beats_file=None, write_beats=write_beats,
                     offset=offset, input_file=cur_file, offsets=offsets)
    print("Finished.")


if __name__ == '__main__':
    main()


