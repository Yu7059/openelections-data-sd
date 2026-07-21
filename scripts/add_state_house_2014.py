"""
Add State House of Representatives race data to 2014 general election results.
Data transcribed from 2014ElectionReturn.pdf pages 26-31.
"""

import csv

# State House data for all 35 districts
# Format: (district, county, candidate, party, votes)
state_house_data = [
    # District 1
    (1, 'Brown', 'Steven D. McCleerey', 'D', 474),
    (1, 'Day', 'Steven D. McCleerey', 'D', 957),
    (1, 'Marshall', 'Steven D. McCleerey', 'D', 737),
    (1, 'Roberts', 'Steven D. McCleerey', 'D', 1799),
    (1, 'Brown', 'Denise A. Rickert', 'D', 845),
    (1, 'Day', 'Denise A. Rickert', 'D', 1188),
    (1, 'Marshall', 'Denise A. Rickert', 'D', 861),
    (1, 'Roberts', 'Denise A. Rickert', 'D', 1218),

    # District 2
    (2, 'Brown', 'John G. Hansen', 'D', 1090),
    (2, 'Clark', 'John G. Hansen', 'D', 270),
    (2, 'Hamlin', 'John G. Hansen', 'D', 385),
    (2, 'Spink', 'John G. Hansen', 'D', 629),
    (2, 'Brown', 'Natasha Housman', 'D', 1264),
    (2, 'Clark', 'Natasha Housman', 'D', 682),
    (2, 'Hamlin', 'Natasha Housman', 'D', 607),
    (2, 'Spink', 'Natasha Housman', 'D', 1199),
    (2, 'Brown', 'Lana Greenfield', 'R', 1287),
    (2, 'Clark', 'Lana Greenfield', 'R', 779),
    (2, 'Hamlin', 'Lana Greenfield', 'R', 1150),
    (2, 'Spink', 'Lana Greenfield', 'R', 1148),
    (2, 'Brown', 'Burton "Butch" Milburn', 'R', 1050),
    (2, 'Clark', 'Burton "Butch" Milburn', 'R', 751),
    (2, 'Hamlin', 'Burton "Butch" Milburn', 'R', 1450),
    (2, 'Spink', 'Burton "Butch" Milburn', 'R', 671),

    # District 3
    (3, 'Brown', 'Bart Evans', 'D', 3404),
    (3, 'Brown', 'Pat Hicks', 'D', 2778),
    (3, 'Brown', 'Donald E. Perle', 'R', 3709),
    (3, 'Brown', 'Al Noorlag', 'R', 3931),

    # District 4
    (4, 'Brookings', 'Kathy Sauthoff', 'D', 1143),
    (4, 'Codington', 'Kathy Sauthoff', 'D', 412),
    (4, 'Deuel', 'Kathy Sauthoff', 'D', 704),
    (4, 'Grant', 'Kathy Sauthoff', 'D', 1331),
    (4, 'Brookings', 'Peggy Schulte', 'D', 843),
    (4, 'Codington', 'Peggy Schulte', 'D', 417),
    (4, 'Deuel', 'Peggy Schulte', 'D', 589),
    (4, 'Grant', 'Peggy Schulte', 'D', 1277),
    (4, 'Brookings', 'Dr. Fred Sherman', 'R', 1600),
    (4, 'Codington', 'Dr. Fred Sherman', 'R', 640),
    (4, 'Deuel', 'Dr. Fred Sherman', 'R', 859),
    (4, 'Grant', 'Dr. Fred Sherman', 'R', 1327),
    (4, 'Brookings', 'John Will', 'R', 1397),
    (4, 'Codington', 'John Will', 'R', 615),
    (4, 'Deuel', 'John Will', 'R', 738),
    (4, 'Grant', 'John Will', 'R', 1182),

    # District 5
    (5, 'Codington', 'Roger W. Hunt', 'R', 4703),
    (5, 'Codington', 'Lee Schoenbeck', 'R', 4754),

    # District 6
    (6, 'Lincoln', 'Richard F. Schremmer', 'D', 1971),
    (6, 'Lincoln', 'Isaac L. Langel', 'D', 3274),
    (6, 'Lincoln', 'Herman Otten', 'R', 4409),

    # District 7
    (7, 'Brookings', 'Spencer Hawley', 'D', 3560),
    (7, 'Brookings', 'Scott "Burt" Erikson', 'R', 3598),

    # District 8
    (8, 'Lake', 'Patrick G. Heemstra', 'D', 968),
    (8, 'Miner', 'Patrick G. Heemstra', 'D', 241),
    (8, 'Moody', 'Patrick G. Heemstra', 'D', 603),
    (8, 'Sanborn', 'Patrick G. Heemstra', 'D', 229),
    (8, 'Lake', 'Jeff Niss', 'D', 2083),
    (8, 'Miner', 'Jeff Niss', 'D', 401),
    (8, 'Moody', 'Jeff Niss', 'D', 864),
    (8, 'Sanborn', 'Jeff Niss', 'D', 296),
    (8, 'Lake', 'Dr. Leslie Her', 'R', 2158),
    (8, 'Miner', 'Dr. Leslie Her', 'R', 351),
    (8, 'Moody', 'Dr. Leslie Her', 'R', 1471),
    (8, 'Sanborn', 'Dr. Leslie Her', 'R', 399),
    (8, 'Lake', 'Matthew Wollman', 'R', 2966),
    (8, 'Miner', 'Matthew Wollman', 'R', 366),
    (8, 'Moody', 'Matthew Wollman', 'R', 870),
    (8, 'Sanborn', 'Matthew Wollman', 'R', 393),

    # District 9
    (9, 'Minnehaha', 'Becky J. Jaspers', 'D', 1882),
    (9, 'Minnehaha', 'Paula M. Erickson', 'D', 2662),
    (9, 'Minnehaha', 'Steve Hickey', 'R', 3027),
    (9, 'Minnehaha', 'Bob S. Grey', 'R', 2654),

    # District 10
    (10, 'Minnehaha', 'Jo Hickman', 'D', 2402),
    (10, 'Minnehaha', 'Jesse W. Welton', 'D', 1769),
    (10, 'Minnehaha', 'Dave Haegele', 'R', 3774),
    (10, 'Minnehaha', 'Steven J. Haugaard', 'R', 3574),

    # District 11
    (11, 'Lincoln', 'Darrell D. Solberg', 'D', 3024),
    (11, 'Lincoln', 'James L. Larson', 'D', 2219),
    (11, 'Lincoln', 'Mark K. Willadsen', 'R', 3770),
    (11, 'Lincoln', 'Jim Hansen', 'R', 4316),

    # District 12
    (12, 'Lincoln', 'Ellen S. Geerlings', 'D', 561),
    (12, 'Minnehaha', 'Ellen S. Geerlings', 'D', 1443),
    (12, 'Lincoln', 'Susan L. Benge', 'D', 899),
    (12, 'Minnehaha', 'Susan L. Benge', 'D', 2282),
    (12, 'Lincoln', 'Alex Jensen', 'R', 1463),
    (12, 'Minnehaha', 'Alex Jensen', 'R', 2069),
    (12, 'Lincoln', 'Arch Beal', 'R', 1632),
    (12, 'Minnehaha', 'Arch Beal', 'R', 2201),

    # District 13
    (13, 'Lincoln', 'Kay Omdahl', 'D', 840),
    (13, 'Minnehaha', 'Kay Omdahl', 'D', 2018),
    (13, 'Lincoln', 'G. Mark Mickelson', 'R', 2518),
    (13, 'Minnehaha', 'G. Mark Mickelson', 'R', 2975),
    (13, 'Lincoln', 'Steve Wiedra', 'R', 2000),
    (13, 'Minnehaha', 'Steve Wiedra', 'R', 2141),

    # District 14
    (14, 'Minnehaha', 'Valarie Lauer-Block', 'D', 3251),
    (14, 'Minnehaha', 'Cris McClure', 'D', 2855),
    (14, 'Minnehaha', 'Larry P. Ziemund', 'R', 4474),
    (14, 'Minnehaha', 'Tom P. Healy', 'R', 4154),

    # District 15
    (15, 'Minnehaha', 'Karen L. Solli', 'D', 1924),
    (15, 'Minnehaha', 'Donald R. Karsky', 'D', 1476),
    (15, 'Minnehaha', 'Eric L. Leggett', 'R', 1323),

    # District 16
    (16, 'Lincoln', 'David L. Anderson', 'R', 1536),
    (16, 'Union', 'David L. Anderson', 'R', 2350),
    (16, 'Lincoln', 'Erin S. Sutton', 'R', 2014),
    (16, 'Union', 'Erin S. Sutton', 'R', 3293),

    # District 17
    (17, 'Clay', 'Ray P. Gunderman', 'D', 2305),
    (17, 'Turner', 'Ray P. Gunderman', 'D', 978),
    (17, 'Clay', 'Melissa S. Garman', 'D', 1595),
    (17, 'Turner', 'Melissa S. Garman', 'D', 1189),
    (17, 'Clay', 'Sheri L. Madsen', 'R', 981),
    (17, 'Turner', 'Sheri L. Madsen', 'R', 1202),
    (17, 'Clay', 'Nancy R. Rom', 'R', 1370),
    (17, 'Turner', 'Nancy R. Rom', 'R', 1909),

    # District 18
    (18, 'Yankton', 'Jay Wismer', 'D', 2336),
    (18, 'Yankton', 'Tony Venhuizen', 'D', 2672),
    (18, 'Yankton', 'Mike Stevens', 'R', 4604),
    (18, 'Yankton', 'Jean Hunhoff', 'R', 3966),

    # District 19
    (19, 'Bon Homme', 'Julie S. Sampson', 'R', 987),
    (19, 'Douglas', 'Julie S. Sampson', 'R', 837),
    (19, 'Hanson', 'Julie S. Sampson', 'R', 683),
    (19, 'Hutchinson', 'Julie S. Sampson', 'R', 2023),
    (19, 'McCook', 'Julie S. Sampson', 'R', 896),
    (19, 'Bon Homme', 'Dean S. Peterson', 'R', 601),
    (19, 'Douglas', 'Dean S. Peterson', 'R', 692),
    (19, 'Hanson', 'Dean S. Peterson', 'R', 706),
    (19, 'Hutchinson', 'Dean S. Peterson', 'R', 1136),
    (19, 'McCook', 'Dean S. Peterson', 'R', 1194),

    # District 20
    (20, 'Aurora', 'James V. Schaefer', 'D', 432),
    (20, 'Davison', 'James V. Schaefer', 'D', 2351),
    (20, 'Jerauld', 'James V. Schaefer', 'D', 379),
    (20, 'Aurora', 'Tara N. Ream', 'R', 602),
    (20, 'Davison', 'Tara N. Ream', 'R', 3400),
    (20, 'Jerauld', 'Tara N. Ream', 'R', 398),
    (20, 'Aurora', 'Jaydeia M. Klaudt', 'R', 648),
    (20, 'Davison', 'Jaydeia M. Klaudt', 'R', 3349),
    (20, 'Jerauld', 'Jaydeia M. Klaudt', 'R', 386),

    # District 21
    (21, 'Bon Homme', 'Calvin A. Gaffera', 'R', 189),
    (21, 'Charles Mix', 'Calvin A. Gaffera', 'R', 947),
    (21, 'Gregory', 'Calvin A. Gaffera', 'R', 302),
    (21, 'Tripp', 'Calvin A. Gaffera', 'R', 326),
    (21, 'Bon Homme', 'Julie A. Bartling', 'D', 367),
    (21, 'Charles Mix', 'Julie A. Bartling', 'D', 1629),
    (21, 'Gregory', 'Julie A. Bartling', 'D', 1198),
    (21, 'Tripp', 'Julie A. Bartling', 'D', 1106),
    (21, 'Bon Homme', 'Lee Quam', 'R', 592),
    (21, 'Charles Mix', 'Lee Quam', 'R', 1743),
    (21, 'Gregory', 'Lee Quam', 'R', 1006),
    (21, 'Tripp', 'Lee Quam', 'R', 1417),

    # District 22
    (22, 'Beadle', 'Peggy Gibson', 'R', 3379),
    (22, 'Kingsbury', 'Peggy Gibson', 'R', 869),
    (22, 'Beadle', 'Lee Wollman', 'D', 1798),
    (22, 'Kingsbury', 'Lee Wollman', 'D', 928),
    (22, 'Beadle', 'Dick Werner', 'R', 3042),
    (22, 'Kingsbury', 'Dick Werner', 'R', 1083),

    # District 23
    (23, 'Campbell', 'Justin Cronin', 'R', 410),
    (23, 'Edmunds', 'Justin Cronin', 'R', 1005),
    (23, 'Faulk', 'Justin Cronin', 'R', 544),
    (23, 'Hand', 'Justin Cronin', 'R', 868),
    (23, 'McPherson', 'Justin Cronin', 'R', 640),
    (23, 'Potter', 'Justin Cronin', 'R', 873),
    (23, 'Spink', 'Justin Cronin', 'R', 156),
    (23, 'Walworth', 'Justin Cronin', 'R', 1191),
    (23, 'Campbell', 'Michelle L. Haman', 'R', 374),
    (23, 'Edmunds', 'Michelle L. Haman', 'R', 851),
    (23, 'Faulk', 'Michelle L. Haman', 'R', 428),
    (23, 'Hand', 'Michelle L. Haman', 'R', 779),
    (23, 'McPherson', 'Michelle L. Haman', 'R', 567),
    (23, 'Potter', 'Michelle L. Haman', 'R', 505),
    (23, 'Spink', 'Michelle L. Haman', 'R', 152),
    (23, 'Walworth', 'Michelle L. Haman', 'R', 1109),

    # District 24
    (24, 'Hughes', 'Tim Rounds', 'R', 4240),
    (24, 'Hyde', 'Tim Rounds', 'R', 337),
    (24, 'Stanley', 'Tim Rounds', 'R', 772),
    (24, 'Sully', 'Tim Rounds', 'R', 426),
    (24, 'Hughes', 'Mary Duvall', 'R', 4725),
    (24, 'Hyde', 'Mary Duvall', 'R', 383),
    (24, 'Stanley', 'Mary Duvall', 'R', 841),
    (24, 'Sully', 'Mary Duvall', 'R', 453),

    # District 25
    (25, 'Minnehaha', 'Kris Langer', 'R', 4367),
    (25, 'Minnehaha', 'Roger S. Gerdes', 'R', 4601),

    # District 26A
    (26, 'Mellette', 'Shawn L. Bordeaux', 'D', 355),
    (26, 'Todd', 'Shawn L. Bordeaux', 'D', 1645),

    # District 26B
    (26, 'Brule', 'Marty Jackley', 'D', 565),
    (26, 'Buffalo', 'Marty Jackley', 'D', 319),
    (26, 'Jones', 'Marty Jackley', 'D', 73),
    (26, 'Lyman', 'Marty Jackley', 'D', 441),
    (26, 'Brule', 'James Schaefer', 'R', 1138),
    (26, 'Buffalo', 'James Schaefer', 'R', 129),
    (26, 'Jones', 'James Schaefer', 'R', 382),
    (26, 'Lyman', 'James Schaefer', 'R', 781),

    # District 27
    (27, 'Bennett', 'Anna M. Tilton-Schield', 'D', 216),
    (27, 'Haakon', 'Anna M. Tilton-Schield', 'D', 74),
    (27, 'Jackson', 'Anna M. Tilton-Schield', 'D', 182),
    (27, 'Pennington', 'Anna M. Tilton-Schield', 'D', 20),
    (27, 'Shannon', 'Anna M. Tilton-Schield', 'D', 1512),
    (27, 'Bennett', 'Kevin K. Miller', 'D', 296),
    (27, 'Haakon', 'Kevin K. Miller', 'D', 125),
    (27, 'Jackson', 'Kevin K. Miller', 'D', 223),
    (27, 'Pennington', 'Kevin K. Miller', 'D', 28),
    (27, 'Shannon', 'Kevin K. Miller', 'D', 2044),
    (27, 'Bennett', 'Elizabeth A. May', 'R', 616),
    (27, 'Haakon', 'Elizabeth A. May', 'R', 719),
    (27, 'Jackson', 'Elizabeth A. May', 'R', 629),
    (27, 'Pennington', 'Elizabeth A. May', 'R', 224),
    (27, 'Shannon', 'Elizabeth A. May', 'R', 388),
    (27, 'Bennett', 'Everett L. Moberg', 'R', 193),
    (27, 'Haakon', 'Everett L. Moberg', 'R', 148),
    (27, 'Jackson', 'Everett L. Moberg', 'R', 165),
    (27, 'Pennington', 'Everett L. Moberg', 'R', 54),
    (27, 'Shannon', 'Everett L. Moberg', 'R', 102),

    # District 28A
    (28, 'Corson', 'Dean G. Winters', 'D', 615),
    (28, 'Dewey', 'Dean G. Winters', 'D', 1108),
    (28, 'Ziebach', 'Dean G. Winters', 'D', 427),

    # District 28B
    (28, 'Butte', 'J. Sam Satter', 'R', 1793),
    (28, 'Harding', 'J. Sam Satter', 'R', 516),
    (28, 'Perkins', 'J. Sam Satter', 'R', 1056),

    # District 29
    (29, 'Butte', 'Dean W. Wiese', 'R', 366),
    (29, 'Meade', 'Dean W. Wiese', 'R', 3621),
    (29, 'Pennington', 'Dean W. Wiese', 'R', 89),
    (29, 'Butte', 'Thomas J. Brunner', 'R', 459),
    (29, 'Meade', 'Thomas J. Brunner', 'R', 3753),
    (29, 'Pennington', 'Thomas J. Brunner', 'R', 121),

    # District 30
    (30, 'Custer', 'Mike Verchio', 'R', 2022),
    (30, 'Fall River', 'Mike Verchio', 'R', 1537),
    (30, 'Pennington', 'Mike Verchio', 'R', 2216),
    (30, 'Custer', 'Lance Russell', 'R', 1961),
    (30, 'Fall River', 'Lance Russell', 'R', 1410),
    (30, 'Pennington', 'Lance Russell', 'R', 2013),
    (30, 'Custer', 'Gunther Gray', 'I', 1263),
    (30, 'Fall River', 'Gunther Gray', 'I', 1258),
    (30, 'Pennington', 'Gunther Gray', 'I', 922),

    # District 31
    (31, 'Lawrence', 'Timothy R. Johns', 'R', 4912),
    (31, 'Lawrence', 'Fred W. Bezanson', 'R', 5550),

    # District 32
    (32, 'Pennington', 'Ritchie A. Huber', 'D', 3007),
    (32, 'Pennington', 'Kristin A. Grand Pre', 'R', 3437),
    (32, 'Pennington', 'Adam Grunin', 'R', 3928),
    (32, 'Pennington', 'Brett M. Monson', 'I', 1230),

    # District 33
    (33, 'Meade', 'Rochelle R. Hagel', 'D', 406),
    (33, 'Pennington', 'Rochelle R. Hagel', 'D', 1888),
    (33, 'Meade', 'Scott W. Odenbach', 'R', 907),
    (33, 'Pennington', 'Scott W. Odenbach', 'R', 3329),
    (33, 'Meade', 'Jacqueline Sly', 'R', 976),
    (33, 'Pennington', 'Jacqueline Sly', 'R', 3553),
    (33, 'Meade', 'Susan E. Hoven', 'I', 298),
    (33, 'Pennington', 'Susan E. Hoven', 'I', 1114),

    # District 34
    (34, 'Pennington', 'Steve H. Sorenson', 'D', 2735),
    (34, 'Pennington', 'Jeff A. Hertsgaard', 'R', 4533),
    (34, 'Pennington', 'Don Dreyer', 'R', 5233),

    # District 35
    (35, 'Pennington', 'Dave Fauske', 'D', 1916),
    (35, 'Pennington', 'Lynne DiSanto', 'R', 3008),
    (35, 'Pennington', 'Blake "Buzz" Camp', 'R', 3509),
]

# Add to existing CSV
output_file = '2014/20141104__sd__general.csv'

with open(output_file, 'a', newline='') as f:
    writer = csv.writer(f)
    for district, county, candidate, party, votes in state_house_data:
        writer.writerow([county, 'State House', district, party, candidate, votes])

print(f"Added {len(state_house_data)} State House rows to {output_file}")
