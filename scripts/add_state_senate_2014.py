"""
Add State Senate race data to 2014 general election results.
Data transcribed from 2014ElectionReturn.pdf pages 22-25.
"""

import csv

# State Senate data for all 35 districts
# Format: (district, county, candidate, party, votes)
state_senate_data = [
    # District 1 - Jason Frerichs (D) - unopposed
    (1, 'Brown', 'Jason Frerichs', 'D', 740),
    (1, 'Day', 'Jason Frerichs', 'D', 1578),
    (1, 'Marshall', 'Jason Frerichs', 'D', 1096),
    (1, 'Roberts', 'Jason Frerichs', 'D', 2239),

    # District 2 - Chuck Wink (R), Brock L. Erickson (R) - both advance
    (2, 'Brown', 'Chuck Wink', 'R', 1657),
    (2, 'Clark', 'Chuck Wink', 'R', 572),
    (2, 'Hamlin', 'Chuck Wink', 'R', 687),
    (2, 'Spink', 'Chuck Wink', 'R', 1220),
    (2, 'Brown', 'Brock L. Erickson', 'R', 1138),
    (2, 'Clark', 'Brock L. Erickson', 'R', 946),
    (2, 'Hamlin', 'Brock L. Erickson', 'R', 1486),
    (2, 'Spink', 'Brock L. Erickson', 'R', 1014),

    # District 3 - Mark Reynold (D), David N. Brown (R)
    (3, 'Brown', 'Mark Reynold', 'D', 3596),
    (3, 'Brown', 'David N. Brown', 'R', 4074),

    # District 4 - Jim Peterson (D) - unopposed
    (4, 'Brookings', 'Jim Peterson', 'D', 1692),
    (4, 'Codington', 'Jim Peterson', 'D', 669),
    (4, 'Deuel', 'Jim Peterson', 'D', 1214),
    (4, 'Grant', 'Jim Peterson', 'D', 1889),

    # District 5 - Reid Helmer (R) - unopposed
    (5, 'Codington', 'Reid Helmer', 'R', 5724),

    # District 6 - Neil Zwinger (D), Gene E. Abels (R)
    (6, 'Lincoln', 'Neil Zwinger', 'D', 1915),
    (6, 'Lincoln', 'Gene E. Abels', 'R', 4877),

    # District 7 - Jay VanDaele (R), Larry Tidemann (R) - both advance
    (7, 'Brookings', 'Jay VanDaele', 'R', 2223),
    (7, 'Brookings', 'Larry Tidemann', 'R', 3729),

    # District 8 - Scott Heidepriem (D), Chuck Jones (R)
    (8, 'Lake', 'Scott Heidepriem', 'D', 2648),
    (8, 'Miner', 'Scott Heidepriem', 'D', 481),
    (8, 'Moody', 'Scott Heidepriem', 'D', 1055),
    (8, 'Sanborn', 'Scott Heidepriem', 'D', 358),
    (8, 'Lake', 'Chuck Jones', 'R', 2111),
    (8, 'Miner', 'Chuck Jones', 'R', 350),
    (8, 'Moody', 'Chuck Jones', 'R', 1290),
    (8, 'Sanborn', 'Chuck Jones', 'R', 437),

    # District 9 - Deb Soholt (R) - unopposed
    (9, 'Minnehaha', 'Deb Soholt', 'R', 4241),

    # District 10 - Michael H. Crump (D), Jenna Heagle (R)
    (10, 'Minnehaha', 'Michael H. Crump', 'D', 2513),
    (10, 'Minnehaha', 'Jenna Heagle', 'R', 4272),

    # District 11 - Tom H. Smith (D), David M. Omdahl (R)
    (11, 'Minnehaha', 'Tom H. Smith', 'D', 3071),
    (11, 'Minnehaha', 'David M. Omdahl', 'R', 4545),

    # District 12 - Jim White (D), Blake Curd (R)
    (12, 'Lincoln', 'Jim White', 'D', 864),
    (12, 'Minnehaha', 'Jim White', 'D', 1972),
    (12, 'Lincoln', 'Blake Curd', 'R', 1751),
    (12, 'Minnehaha', 'Blake Curd', 'R', 2514),

    # District 13 - Phyllis J. Heinemann (R) - unopposed
    (13, 'Lincoln', 'Phyllis J. Heinemann', 'R', 2796),
    (13, 'Minnehaha', 'Phyllis J. Heinemann', 'R', 3349),

    # District 14 - Deb J. Soholt (R) - unopposed
    (14, 'Minnehaha', 'Deb J. Soholt', 'R', 6023),

    # District 15 - Angie D. O'Dell (D) - unopposed
    (15, 'Minnehaha', 'Angie D. O\'Dell', 'D', 2349),

    # District 16 - Jim Bradford (D), Dan Lederman (R)
    (16, 'Lincoln', 'Jim Bradford', 'D', 1333),
    (16, 'Union', 'Jim Bradford', 'D', 2210),
    (16, 'Lincoln', 'Dan Lederman', 'R', 1570),
    (16, 'Union', 'Dan Lederman', 'R', 2872),

    # District 17 - Michelle L. Stevens (D), Arthur L. Rusch (R)
    (17, 'Clay', 'Michelle L. Stevens', 'D', 1744),
    (17, 'Turner', 'Michelle L. Stevens', 'D', 1054),
    (17, 'Clay', 'Arthur L. Rusch', 'R', 1936),
    (17, 'Turner', 'Arthur L. Rusch', 'R', 1937),

    # District 18 - Bernie L. Hunhoff (D), Matt Soenne (R)
    (18, 'Yankton', 'Bernie L. Hunhoff', 'D', 4300),
    (18, 'Yankton', 'Matt Soenne', 'R', 3403),

    # District 19 - Bill L. Van Gerpen (R) - unopposed
    (19, 'Bon Homme', 'Bill L. Van Gerpen', 'R', 1115),
    (19, 'Douglas', 'Bill L. Van Gerpen', 'R', 1099),
    (19, 'Hanson', 'Bill L. Van Gerpen', 'R', 929),
    (19, 'Hutchinson', 'Bill L. Van Gerpen', 'R', 2141),
    (19, 'McCook', 'Bill L. Van Gerpen', 'R', 1345),

    # District 20 - Mike Verchio (R) - unopposed
    (20, 'Aurora', 'Mike Verchio', 'R', 790),
    (20, 'Davison', 'Mike Verchio', 'R', 4592),
    (20, 'Jerauld', 'Mike Verchio', 'R', 549),

    # District 21 - Billie J. Sutton (D) - unopposed
    (21, 'Bon Homme', 'Billie J. Sutton', 'D', 594),
    (21, 'Charles Mix', 'Billie J. Sutton', 'D', 2310),
    (21, 'Gregory', 'Billie J. Sutton', 'D', 1394),
    (21, 'Tripp', 'Billie J. Sutton', 'D', 1523),

    # District 22 - Darrell Isaak (D), Jim White (R)
    (22, 'Beadle', 'Darrell Isaak', 'D', 1562),
    (22, 'Kingsbury', 'Darrell Isaak', 'D', 637),
    (22, 'Beadle', 'Jim White', 'R', 3888),
    (22, 'Kingsbury', 'Jim White', 'R', 1292),

    # District 23 - Casey Crabtree (R) - unopposed
    (23, 'Campbell', 'Casey Crabtree', 'R', 506),
    (23, 'Edmunds', 'Casey Crabtree', 'R', 1203),
    (23, 'Faulk', 'Casey Crabtree', 'R', 653),
    (23, 'Hand', 'Casey Crabtree', 'R', 1019),
    (23, 'McPherson', 'Casey Crabtree', 'R', 800),
    (23, 'Potter', 'Casey Crabtree', 'R', 975),
    (23, 'Spink', 'Casey Crabtree', 'R', 191),
    (23, 'Walworth', 'Casey Crabtree', 'R', 1480),

    # District 24 - Ruth Buffalo (D), Jeff Monroe (R)
    (24, 'Hughes', 'Ruth Buffalo', 'D', 2960),
    (24, 'Hyde', 'Ruth Buffalo', 'D', 163),
    (24, 'Stanley', 'Ruth Buffalo', 'D', 503),
    (24, 'Sully', 'Ruth Buffalo', 'D', 185),
    (24, 'Hughes', 'Jeff Monroe', 'R', 3822),
    (24, 'Hyde', 'Jeff Monroe', 'R', 409),
    (24, 'Stanley', 'Jeff Monroe', 'R', 758),
    (24, 'Sully', 'Jeff Monroe', 'R', 489),

    # District 25 - Bill L. Lynd (D), Tim R. Goodwin (R)
    (25, 'Minnehaha', 'Bill L. Lynd', 'D', 2577),
    (25, 'Minnehaha', 'Tim R. Goodwin', 'R', 5492),

    # District 26 - Troy E. Heinert (D), John K. Kausen (R)
    (26, 'Brule', 'Troy E. Heinert', 'D', 647),
    (26, 'Buffalo', 'Troy E. Heinert', 'D', 333),
    (26, 'Jones', 'Troy E. Heinert', 'D', 135),
    (26, 'Lyman', 'Troy E. Heinert', 'D', 480),
    (26, 'Mellette', 'Troy E. Heinert', 'D', 370),
    (26, 'Todd', 'Troy E. Heinert', 'D', 1782),
    (26, 'Todd', 'John K. Kausen', 'R', 405),

    # District 27 - Jim Bradford (D) - unopposed (write-in?)
    (27, 'Bennett', 'Jim Bradford', 'D', 614),
    (27, 'Haakon', 'Jim Bradford', 'D', 333),
    (27, 'Jackson', 'Jim Bradford', 'D', 467),
    (27, 'Pennington', 'Jim Bradford', 'D', 72),
    (27, 'Shannon', 'Jim Bradford', 'D', 2374),

    # District 28 - Lynn L. Lucas (D), Betty J. Olson (R)
    (28, 'Butte', 'Lynn L. Lucas', 'D', 706),
    (28, 'Corson', 'Lynn L. Lucas', 'D', 463),
    (28, 'Dewey', 'Lynn L. Lucas', 'D', 1095),
    (28, 'Harding', 'Lynn L. Lucas', 'D', 210),
    (28, 'Perkins', 'Lynn L. Lucas', 'D', 455),
    (28, 'Ziebach', 'Lynn L. Lucas', 'D', 388),
    (28, 'Butte', 'Betty J. Olson', 'R', 1651),
    (28, 'Corson', 'Betty J. Olson', 'R', 456),
    (28, 'Dewey', 'Betty J. Olson', 'R', 379),
    (28, 'Harding', 'Betty J. Olson', 'R', 391),
    (28, 'Perkins', 'Betty J. Olson', 'R', 881),
    (28, 'Ziebach', 'Betty J. Olson', 'R', 239),

    # District 29 - Gary L. Cammack (R) - unopposed
    (29, 'Butte', 'Gary L. Cammack', 'R', 564),
    (29, 'Meade', 'Gary L. Cammack', 'R', 4910),
    (29, 'Pennington', 'Gary L. Cammack', 'R', 143),

    # District 30 - Bruce R. Kollbaum (R) - unopposed
    (30, 'Custer', 'Bruce R. Kollbaum', 'R', 2482),
    (30, 'Fall River', 'Bruce R. Kollbaum', 'R', 1938),
    (30, 'Pennington', 'Bruce R. Kollbaum', 'R', 2664),

    # District 31 - Bob E. Ewing (R) - unopposed
    (31, 'Lawrence', 'Bob E. Ewing', 'R', 6318),

    # District 32 - Alan D. Solano (R) - unopposed
    (32, 'Pennington', 'Alan D. Solano', 'R', 5134),

    # District 33 - Robin A. Schaff (D), Phil Jensen (R)
    (33, 'Meade', 'Robin A. Schaff', 'D', 517),
    (33, 'Pennington', 'Robin A. Schaff', 'D', 2226),
    (33, 'Meade', 'Phil Jensen', 'R', 1121),
    (33, 'Pennington', 'Phil Jensen', 'R', 3895),

    # District 34 - Craig Tieszen (R) - unopposed
    (34, 'Pennington', 'Craig Tieszen', 'R', 6776),

    # District 35 - Terri Haverly (R) - unopposed
    (35, 'Pennington', 'Terri Haverly', 'R', 3901),
]

# Add to existing CSV
output_file = '2014/20141104__sd__general.csv'

with open(output_file, 'a', newline='') as f:
    writer = csv.writer(f)
    for district, county, candidate, party, votes in state_senate_data:
        writer.writerow([county, 'State Senate', district, party, candidate, votes])

print(f"Added {len(state_senate_data)} State Senate rows to {output_file}")
