from wresty.core import WrestyGrabber


# venue_id = '679'  # loring place, no cancellation fee
venue_id = '71199'  # gp's
# venue_id = '2492'  # 4 horseman
# venue_id = '834'  # 4 charles
# venue_id = '1505'  # don angie
# venue_id = '52984'  # saint theo's
# venue_id = '5771'  # rezdora
# venue_id = '2567'  # via carota
# venue_id = '9846'  # minetta tavern
# venue_id = '35676'  # cote
# venue_id = '58848'  # laser wolf


# 18 seconds for 100 attempts

wresty = WrestyGrabber(venue_id=venue_id, email='jesse.brian.shapiro@gmail.com')
wresty.continuously_try_to_book(date='2023-07-02', party_size=2, start_time='19:15', end_time='21:15', use_concierge=False)
