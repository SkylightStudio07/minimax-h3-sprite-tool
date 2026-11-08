"""Experimental pixel attack prompts with explicit turning/jumping constraints.

Not yet exposed as site presets. Save observed results before treating a prompt
as a proven action recipe. Source character/weapon are supplied by an image.
"""
TEMPLATES={
 'spin_slash':dict(label='돌려베기',seed=2026101961,allowFacingChange=True,
  requestedPhases=['준비','360도 몸 회전과 베기','회전 제동','오른쪽 대기 복귀'],
  motion=(
   'Perform ONE grounded FULL-BODY SPINNING SWORD SLASH, exactly ONE 360-degree turn about the vertical body axis. '
   'At 0.0-0.45 seconds she bends both knees slightly, draws the sword out to the side, and loads weight on her front boot. '
   'At 0.45-1.9 seconds her feet pivot and her HIPS, TORSO, SHOULDERS AND HEAD visibly rotate together through a full turn. '
   'Briefly show the BACK of the coat and the back of her ponytail midway through the turn; this is a real body turn, NOT merely a sword circle while the torso stays right-facing. '
   'The sword arm extends outward and the one rigid sword sweeps one broad horizontal arc around her at waist/chest height. '
   'Her empty arm folds closer to the torso for balance. The ponytail and split skirt flare outward from rotational momentum, following the body with a small delay. '
   'At 1.9-2.6 seconds she completes the full turn facing SCREEN RIGHT again, plants the forward boot, and brakes into a clear low follow-through pose. '
   'From 2.6 seconds onward she regains the exact opening ready stance, right-facing and at the opening horizontal position. '
   'One controlled spin only; keep the boots close to the same ground line, no airborne somersault, no repeated pirouettes, no skating across the screen. '
   'A short pale-cyan crescent trails only the moving sword edge during the fast part; it fades completely as the turn ends. '
   'Do not make a solid glowing energy sphere or a continuous ring hiding the body. Let the changing front/back body silhouette remain readable.')),
 'jump_slam':dict(label='점프 후 내려찍기',seed=2026101962,allowFacingChange=False,
  requestedPhases=['웅크리기','양발 도약','공중에서 검 들어올리기','낙하 베기','착지 타격','회복'],
  motion=(
   'Perform ONE JUMPING OVERHEAD SWORD SLAM, not a standing attack and not repeated jumps. '
   'At 0.0-0.5 seconds she visibly crouches, bends both knees, lowers the hips and draws the sword behind and above her shoulder. '
   'At 0.5-1.35 seconds she pushes off strongly with BOTH boots, lifting the whole body upward by about half her standing height. '
   'Show a CLEAR EMPTY GAP between BOTH boots and the original ground line. The camera and ground line do NOT move. '
   'Near 1.35-1.9 seconds she reaches the apex: both feet airborne, knees tucked slightly, torso upright, the sword raised overhead with her sword arm ready to strike. '
   'At 1.9-2.4 seconds she falls and whips the sword DOWNWARD in front of her toward screen right, following the falling body into a strong diagonal ground-directed cut. '
   'At 2.4-2.8 seconds both boots return to the SAME original ground line. The front knee bends deeply to absorb landing, torso leans into the sword follow-through. '
   'A compact pale-cyan vertical slash follows the blade during descent, then ONE small gold impact burst appears beside the ground-level sword tip at landing. '
   'From 2.8 seconds onward she rises naturally out of the landing crouch to the opening right-facing ready stance and opening horizontal position. '
   'Remain a strict SCREEN-RIGHT side profile for every phase, including takeoff/apex/landing. No body spin, no facing the viewer, no midair flips, no flight or hovering. '
   'Ponytail and skirt lift after takeoff, trail upward during descent and settle after landing. No large dust cloud obscuring the boots.'))
}
COMMON=(
 'Preserve the EXACT pixel-art woman supplied by the opening image: auburn high ponytail, cream short military jacket, dark teal split battle skirt over dark trousers, brown gloves and knee-high brown boots. '
 'Keep her adult build, original face and head-to-body proportions, costume geometry, small square pixel clusters and limited palette; do not redraw as smooth anime or a painted illustration. '
 'Keep ONE rigid silver straight sword with the same brown hilt connected to the same sword hand throughout. The empty hand stays empty. No duplicated weapon, detached sword, stretching blade, hand swapping or local body inflation. '
 'The subject keeps the SAME input screen scale; do not enlarge the character when moving. Use the large empty margins above and on both sides for motion and compact effects. '
 'Retain the same original boot ground line on takeoff and landing; the background is a featureless medium-grey colour field, not a rendered floor or scene. '
 'FIXED orthographic side-scrolling camera with identical framing, no camera rotation, pan, tilt, zoom, shake, cuts, perspective orbit or added scenery. '
 'Keep the whole body, ponytail, both boots, sword and effects inside the canvas. No cast shadow, text, captions or other characters. '
 'Perform the action once with readable anticipation, execution, follow-through and recovery, then return to the opening ready pose. '
)

def build_prompt(template_id,duration):
 item=TEMPLATES[template_id]
 alignment=f'<Picture 1> supplies the opening image of [Shot 1] at 0.00 seconds. <Picture 2> supplies its closing image at {duration:.2f} seconds; both images show the same composition.'
 # Unlike the standard right-facing wrapper, spin_slash must allow the actor
 # to turn. Only the camera stays fixed; do not append a contradictory facing lock.
 return alignment+'\n\nintegrated_multimodal_description: [Shot 1] '+COMMON+item['motion']+f' Complete the final recovery by {duration:.2f} seconds.'+'\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A'
